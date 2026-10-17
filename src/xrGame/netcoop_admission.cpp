// Exception-enabled, no engine/PCH headers (doc 135). Every HTTP call runs on
// the coordinator thread; the simulation thread only queues and polls.
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include "netcoop_admission.h"
#include "netcoop_checkpoint_worker.h"
#include "netcoop_player_checkpoint.h"
#include <algorithm>
#include <condition_variable>
#include <cstring>
#include <deque>
#include <filesystem>
#include <fstream>
#include <map>
#include <mutex>
#include <thread>

namespace netcoop_world
{
#ifdef _WIN32
namespace
{
constexpr std::uint64_t maximum=0x7fffffffffffffffULL;
constexpr unsigned lease_ms=15000;
std::string text(const char* value,std::size_t limit)
{
    if(!value) return std::string();
    std::size_t length=0;while(length<=limit && value[length]) ++length;
    if(length>limit) throw std::invalid_argument("admission text budget");
    return std::string(value,length);
}
std::string lower(std::string value)
{
    for(char& c:value) if(c>='A' && c<='Z') c=char(c-'A'+'a');
    return value;
}
std::string random_hex()
{
    unsigned char bytes[16]{};
    if(BCryptGenRandom(nullptr,bytes,sizeof(bytes),BCRYPT_USE_SYSTEM_PREFERRED_RNG)<0)
        throw std::runtime_error("admission identity unavailable");
    return checkpoint_hex_bytes(std::string(reinterpret_cast<const char*>(bytes),sizeof(bytes)));
}
template<std::size_t N> void put(char (&target)[N],const std::string& value)
{
    const auto count=std::min(value.size(),N-1);std::memcpy(target,value.data(),count);target[count]=0;
}
std::string key(const std::string& account,unsigned slot){return lower(account)+":"+std::to_string(slot);}
}

struct AdmissionCoordinator::State
{
    // One admitted character: the master versions the next capture builds on.
    struct Character
    {
        std::string id,account;
        unsigned slot=0;
        std::uint64_t session=0,version=0,revision=0,generation=0,last=0;
        std::vector<std::uint64_t> outstanding; // submitted, not yet retired
        bool leaving=false;
    };
    enum class Kind { Admit,Leave,Depart };
    struct Job
    {
        Kind kind=Kind::Admit;
        std::uint64_t ticket=0,deadline=0;
        std::string account,local,token,target;
        unsigned slot=0;
    };
    struct Outcome
    {
        AdmissionResult admission;
        DepartureResult departure;
        std::vector<unsigned char> bytes;
        bool final=false;
    };

    std::string config_path,location,instance;
    std::wstring spool;
    WriterConfig config;
    CheckpointWorker worker;
    std::mutex lock;
    std::condition_variable wake;
    std::deque<Job> jobs;
    std::map<std::uint64_t,Outcome> outcomes;
    std::map<std::string,Character> characters; // key(account,slot)
    std::uint64_t next_ticket=1,epoch=0,fence=0;
    bool stopping=false,ready=false,failed=false;
    std::thread thread;

    State(std::string file,std::string map,std::wstring directory)
        :config_path(std::move(file)),location(std::move(map)),instance(random_hex()),spool(std::move(directory))
    { thread=std::thread([this]{run();}); }

    bool request(const std::string& method,const std::string& path,const std::string& payload,BridgeJson& result,unsigned& status)
    { return writer_request(config,instance,epoch,method,path,payload,result,status); }
    // One master command, the SAME command ID on every retry, until a reply,
    // a permanent refusal or the deadline.
    CheckpointStep command(const std::string& operation,const BridgeJson& arguments,BridgeJson& result,std::uint64_t deadline,
        const std::string& id=std::string())
    {
        const auto command_id=id.empty() ? random_hex():id;
        const auto payload=BridgeJson{{"command_id",command_id},{"operation",operation},{"arguments",arguments}}.dump();
        for(;;)
        {
            unsigned status=0;
            if(request("POST","/v1/command",payload,result,status)) return CheckpointStep::Complete;
            if(checkpoint_failure(status)==CheckpointStep::Rejected) return CheckpointStep::Rejected;
            if(GetTickCount64()>=deadline || halted()) return CheckpointStep::Retry;
            pause(250);
        }
    }
    bool halted(){std::lock_guard<std::mutex> guard(lock);return stopping;}
    void pause(unsigned ms)
    {
        std::unique_lock<std::mutex> guard(lock);
        wake.wait_for(guard,std::chrono::milliseconds(ms),[this]{return stopping;});
    }

    // Lease, adoption of this location's records, checkpoint worker.
    bool open()
    {
        {
            std::ifstream file(config_path,std::ios::binary);char encoded[4097];
            if(!file) return false;
            file.read(encoded,sizeof(encoded));
            config=WriterConfig::parse(std::string(encoded,std::size_t(file.gcount())),location);
        }
        const auto deadline=GetTickCount64()+120000; // the master may still be starting
        BridgeJson clock;
        for(;;)
        {
            unsigned status=0;
            if(writer_request(config,instance,0,"GET","/v1/clock","",clock,status)) break;
            if(GetTickCount64()>=deadline || halted()) return false;
            pause(1000);
        }
        if(bridge_unsigned(clock,"world_id")!=config.world || bridge_unsigned(clock,"seed")!=config.seed) return false;
        epoch=bridge_unsigned(clock,"authority_epoch");
        if(!epoch || epoch>maximum) return false;
        BridgeJson claim;
        const auto claim_deadline=GetTickCount64()+60000;
        // Another owner's lease of this location (a previous run) expires
        // after its TTL; the claim is retried with the same command ID.
        const auto claim_id=random_hex();
        for(;;)
        {
            const auto step=command("location_claim",{{"location",location},{"capacity",128},{"ttl_ms",lease_ms}},claim,claim_deadline,claim_id);
            if(step==CheckpointStep::Complete) break;
            if(GetTickCount64()>=claim_deadline || halted()) return false;
            pause(1000);
        }
        fence=bridge_unsigned(claim,"fence");
        if(!fence || fence>maximum || claim.value("location",std::string())!=location) return false;
        BridgeJson recovered;
        if(command("location_recover",{{"location",location},{"fence",fence}},recovered,GetTickCount64()+30000)!=CheckpointStep::Complete)
            return false;
        // A capture spooled by an earlier run (another instance or fence) can
        // never be finished: every capture is a complete image of the local
        // file, so the next one supersedes it. Only this run's folder stays.
        CreateDirectoryW(spool.c_str(),nullptr);
        const std::wstring folder=L"run_"+std::to_wstring(fence)+L"_"+std::wstring(instance.begin(),instance.end());
        {
            std::error_code error;
            for(const auto& entry:std::filesystem::directory_iterator(spool,error))
                if(entry.is_directory(error) && entry.path().filename().wstring()!=folder)
                    std::filesystem::remove_all(entry.path(),error);
        }
        const auto directory=spool+L"\\"+folder;
        CheckpointWorkerScope scope;
        put(scope.location,location);put(scope.instance,instance);
        scope.world=config.world;scope.seed=config.seed;scope.epoch=epoch;scope.fence=fence;scope.lease_ms=lease_ms;
        if(!worker.start(config_path.c_str(),directory.c_str(),scope)) return false;
        const auto ready_deadline=GetTickCount64()+30000;
        for(;;)
        {
            const auto worker_status=worker.status();
            if(worker_status.ready) return true;
            if(worker_status.configuration_error || worker_status.authority_lost || GetTickCount64()>=ready_deadline || halted())
                return false;
            pause(100);
        }
    }

    void finish(std::uint64_t ticket,Outcome&& outcome)
    {
        std::lock_guard<std::mutex> guard(lock);
        outcome.final=true;outcomes[ticket]=std::move(outcome);
    }
    void refuse(const Job& job,const std::string& reason,AdmissionState state=AdmissionState::Refused)
    {
        Outcome outcome;
        if(job.kind==Kind::Depart) {outcome.departure.state=DepartureState::Refused;put(outcome.departure.reason,reason);}
        else {outcome.admission.state=state;put(outcome.admission.reason,reason);}
        finish(job.ticket,std::move(outcome));
    }

    // Waits until the newest capture of this character is durable (and
    // retires it), so the master holds the newest image before a handoff.
    bool settle(Character& character,std::uint64_t deadline)
    {
        if(!character.last) return true;
        for(;;)
        {
            // The worker sends one character's captures in order and keeps a
            // durable one until it is released: release while waiting.
            retire(character.id,character.outstanding);
            CheckpointWorkerResult result;
            const bool polled=worker.poll(character.id.c_str(),character.last,result);
            if(!polled) break; // already retired
            if(result.state==CheckpointCaptureState::Durable)
            {
                if(result.version) character.version=result.version;
                if(result.revision) character.revision=result.revision;
                break;
            }
            if(result.state==CheckpointCaptureState::Rejected) return false;
            if(GetTickCount64()>=deadline || halted()) return false;
            pause(100);
        }
        retire(character.id,character.outstanding);
        return true;
    }
    // Retires durable captures (the worker keeps each until released).
    void retire(const std::string& id,std::vector<std::uint64_t>& generations)
    {
        for(auto it=generations.begin();it!=generations.end();)
        {
            CheckpointWorkerResult result;
            if(!worker.poll(id.c_str(),*it,result)) {it=generations.erase(it);continue;}
            if(result.state==CheckpointCaptureState::Durable && worker.release(id.c_str(),*it)) {++it;continue;}
            ++it;
        }
    }
    void sweep()
    {
        std::vector<std::pair<std::string,std::vector<std::uint64_t>>> work;
        {
            std::lock_guard<std::mutex> guard(lock);
            for(const auto& entry:characters) if(!entry.second.outstanding.empty()) work.emplace_back(entry.first,entry.second.outstanding);
        }
        for(auto& item:work)
        {
            std::string id;
            {
                std::lock_guard<std::mutex> guard(lock);
                auto found=characters.find(item.first);if(found==characters.end()) continue;
                id=found->second.id;
            }
            const auto before=item.second;
            retire(id,item.second);
            std::lock_guard<std::mutex> guard(lock);
            auto found=characters.find(item.first);if(found==characters.end()) continue;
            auto& list=found->second.outstanding;
            // Drop the generations this pass saw retired; keep newer ones.
            for(const auto generation:before)
                if(std::find(item.second.begin(),item.second.end(),generation)==item.second.end())
                    list.erase(std::remove(list.begin(),list.end(),generation),list.end());
        }
    }

    void admit(const Job& job)
    {
        const auto account=lower(job.account);
        const auto id=checkpoint_player_id(config.world,config.seed,account,job.slot);
        BridgeJson result;
        // A level changer's handoff: claim and commit the frozen character.
        // A token the master refuses for good (the passage was finished,
        // aborted or expired; owner 2026-10-17: refused at every login after
        // a reconnect) is stale: it is dropped and the login goes on as usual.
        bool stale_token=false;
        if(!job.token.empty())
        {
            const auto claim=command("transfer_claim",{{"token",job.token},{"target_fence",fence}},result,job.deadline);
            if(claim==CheckpointStep::Retry)
                return refuse(job,"the world master did not answer for this passage",AdmissionState::Unavailable);
            // A refusal leaves no result object to read.
            const bool reply=claim==CheckpointStep::Complete && result.is_object();
            const auto transfer=reply ? result.value("id",std::string()):std::string();
            if(!reply || !checkpoint_hex(transfer,32) || result.value("entity_id",std::string())!=id)
                stale_token=true;
            else if(result.value("state",std::string())!="COMMITTED" &&
                command("transfer_commit",{{"transfer_id",transfer},{"target_fence",fence}},result,job.deadline)!=CheckpointStep::Complete)
                return refuse(job,"the transfer could not be committed by the world master");
        }
        const auto finish_admission=[&](Outcome&& outcome){outcome.admission.stale_token=stale_token;finish(job.ticket,std::move(outcome));};
        PlayerSlotObservation slot;unsigned status=0;
        for(;;)
        {
            const auto step=inspect_player_slot(config,instance,epoch,account,job.slot,fence,slot,status);
            if(step==CheckpointStep::Complete) break;
            if(step==CheckpointStep::Rejected)
                return refuse(job,status==409 ? "the character is active, in transit or has an unfinished save on another location":
                    "the world master refused this character slot");
            if(GetTickCount64()>=job.deadline || halted()) return refuse(job,"the world master did not answer",AdmissionState::Unavailable);
            pause(250);
        }
        if(slot.state==PlayerSlotStatus::Elsewhere)
        {
            Outcome outcome;
            outcome.admission.state=AdmissionState::Elsewhere;
            put(outcome.admission.home,slot.home);
            put(outcome.admission.reason,"the character is on "+slot.home);
            return finish_admission(std::move(outcome));
        }
        Character character;
        character.id=id;character.account=account;character.slot=job.slot;
        if(slot.state==PlayerSlotStatus::Absent)
        {
            // A new character, or one older than the master: its local file
            // becomes the first checkpoint with the first capture.
            if(command("entity_create",{{"entity_id",id},{"kind","CHARACTER"},{"location",location},{"fence",fence},
                {"state",BridgeJson::object()},{"account",account}},result,job.deadline)!=CheckpointStep::Complete)
                return refuse(job,"the world master could not register this character");
            character.version=bridge_unsigned(result,"version");character.session=1;character.revision=0;
        }
        else if(slot.state==PlayerSlotStatus::Disconnected)
        {
            if(command("session_resume",{{"character_id",id},{"location",location},{"fence",fence},{"version",slot.entity_version}},
                result,job.deadline)!=CheckpointStep::Complete)
                return refuse(job,"the world master could not resume this character here");
            character.version=bridge_unsigned(result,"version");character.session=bridge_unsigned(result,"session_fence");
            character.revision=slot.revision;
        }
        else if(slot.state==PlayerSlotStatus::Active)
        {
            character.version=slot.entity_version;character.session=slot.session_fence;character.revision=slot.revision;
        }
        else return refuse(job,"this character slot has an unactivated import on the world master",AdmissionState::Unavailable);
        if(!character.version || !character.session) return refuse(job,"the world master returned an invalid session");
        std::uint64_t floor=0;worker.generation_floor(id.c_str(),floor);
        character.generation=floor;
        Outcome outcome;
        outcome.admission.state=AdmissionState::Admitted;put(outcome.admission.character,id);
        outcome.admission.revision=character.revision;
        // The master's durable image wins over a different local file.
        const auto local_sha=job.local.empty() ? std::string():checkpoint_sha256(job.local);
        if(character.revision && slot.sha256!=local_sha)
        {
            CheckpointDownload read(id,fence,character.session,character.revision,slot.sha256,std::size_t(slot.bytes));
            auto send=[this](const std::string& method,const std::string& path,const std::string& payload,BridgeJson& reply,unsigned& code)
            { return request(method,path,payload,reply,code); };
            for(;;)
            {
                const auto step=read.step(send);
                if(step==CheckpointStep::Complete) break;
                if(step==CheckpointStep::Rejected) return refuse(job,"the world master's checkpoint could not be read");
                if(step==CheckpointStep::Retry)
                {
                    if(GetTickCount64()>=job.deadline || halted()) return refuse(job,"the world master's checkpoint read timed out");
                    pause(250);
                }
            }
            const auto& raw=read.bytes();
            outcome.bytes.assign(raw.begin(),raw.end());outcome.admission.master_bytes=true;
        }
        {
            std::lock_guard<std::mutex> guard(lock);
            characters[key(account,job.slot)]=std::move(character);
        }
        finish_admission(std::move(outcome));
    }

    bool take(const Job& job,Character& character)
    {
        std::lock_guard<std::mutex> guard(lock);
        auto found=characters.find(key(job.account,job.slot));
        if(found==characters.end()) return false;
        character=found->second;return true;
    }
    void forget(const Job& job)
    {
        std::lock_guard<std::mutex> guard(lock);
        characters.erase(key(job.account,job.slot));
    }
    void leave(const Job& job)
    {
        Character character;
        if(!take(job,character)) return finish(job.ticket,Outcome{});
        const bool durable=settle(character,job.deadline);
        BridgeJson result;
        // An unfinished capture blocks the disconnect on the master; the
        // character stays ACTIVE there and the next login resumes it as is.
        if(durable)
            command("session_disconnect",{{"character_id",character.id},{"fence",fence},{"version",character.version},
                {"state",BridgeJson::object()}},result,job.deadline);
        forget(job);
        finish(job.ticket,Outcome{});
    }
    void depart(const Job& job)
    {
        Character character;
        if(!take(job,character)) return refuse(job,"the character is not admitted through the world master");
        if(!settle(character,job.deadline)) return refuse(job,"the character's last save has not reached the world master");
        BridgeJson result;
        if(command("transfer_prepare",{{"entity_id",character.id},{"source",location},{"source_fence",fence},
            {"target",job.target},{"entity_version",character.version},{"ttl_ms",300000}},result,job.deadline)!=CheckpointStep::Complete)
            return refuse(job,"the world master refused the passage (the target location is unavailable or full)");
        const auto token=result.value("token",std::string());
        if(token.empty() || token.size()>2048) return refuse(job,"the world master returned an invalid transfer");
        forget(job);
        Outcome outcome;outcome.departure.state=DepartureState::Ready;put(outcome.departure.token,token);
        finish(job.ticket,std::move(outcome));
    }

    void run() noexcept
    {
        bool opened=false;
        try{opened=open();}catch(...){opened=false;}
        {
            std::lock_guard<std::mutex> guard(lock);
            ready=opened;failed=!opened;wake.notify_all();
        }
        for(;;)
        {
            Job job;
            bool idle=false;
            {
                std::unique_lock<std::mutex> guard(lock);
                wake.wait_for(guard,std::chrono::milliseconds(500),[this]{return stopping || !jobs.empty();});
                if(jobs.empty())
                {
                    if(stopping) break;
                    idle=true;
                }
                else {job=std::move(jobs.front());jobs.pop_front();}
            }
            if(idle)
            {
                if(opened) try{sweep();}catch(...){}
                continue;
            }
            try
            {
                if(!opened) refuse(job,"the world master is unavailable",AdmissionState::Unavailable);
                else if(job.kind==Kind::Admit) admit(job);
                else if(job.kind==Kind::Leave) leave(job);
                else depart(job);
            }
            catch(...){refuse(job,"the world master exchange failed",AdmissionState::Unavailable);}
        }
        worker.stop();
    }
    std::uint64_t queue(Job&& job)
    {
        std::lock_guard<std::mutex> guard(lock);
        if(stopping || jobs.size()>1024) return 0;
        job.ticket=next_ticket++;
        const auto ticket=job.ticket;
        jobs.push_back(std::move(job));wake.notify_all();
        return ticket;
    }
};

AdmissionCoordinator::~AdmissionCoordinator(){stop();}
bool AdmissionCoordinator::start(const char* config_path,const char* location,const wchar_t* spool_path) noexcept
{
    stop();
    try
    {
        const auto config=text(config_path,2048),map=text(location,64);
        if(config.empty() || map.empty() || !spool_path) return false;
        if(GetFileAttributesA(config.c_str())==INVALID_FILE_ATTRIBUTES) return false;
        std::size_t length=0;while(length<=2048 && spool_path[length]) ++length;
        if(!length || length>2048) return false;
        state_=new State(config,map,std::wstring(spool_path,length));
        return true;
    }
    catch(...){state_=nullptr;return false;}
}
CoordinatorStatus AdmissionCoordinator::status() noexcept
{
    CoordinatorStatus result;
    if(!state_) return result;
    try
    {
        std::lock_guard<std::mutex> guard(state_->lock);
        result.started=true;result.ready=state_->ready && !state_->stopping;result.failed=state_->failed;
        result.epoch=state_->epoch;result.fence=state_->fence;
        result.characters=unsigned(state_->characters.size());result.pending=unsigned(state_->jobs.size());
    }
    catch(...){}
    return result;
}
std::uint64_t AdmissionCoordinator::admit(const char* account,unsigned slot,const void* local,std::size_t local_size,const char* token) noexcept
{
    try
    {
        if(!state_ || local_size>checkpoint_limit || (local_size && !local)) return 0;
        State::Job job;job.kind=State::Kind::Admit;
        job.account=text(account,20);job.slot=slot;job.token=text(token,2048);
        if(local_size) job.local.assign(static_cast<const char*>(local),local_size);
        if(job.account.size()<3 || slot<1 || slot>10) return 0;
        job.deadline=GetTickCount64()+30000;
        return state_->queue(std::move(job));
    }
    catch(...){return 0;}
}
bool AdmissionCoordinator::poll_admission(std::uint64_t ticket,AdmissionResult& result,std::vector<unsigned char>& bytes) noexcept
{
    result={};bytes.clear();
    try
    {
        if(!state_) {result.state=AdmissionState::Unavailable;return true;}
        std::lock_guard<std::mutex> guard(state_->lock);
        auto found=state_->outcomes.find(ticket);
        if(found==state_->outcomes.end()) return false;
        result=found->second.admission;bytes.swap(found->second.bytes);
        state_->outcomes.erase(found);return true;
    }
    catch(...){result={};result.state=AdmissionState::Unavailable;return true;}
}
bool AdmissionCoordinator::capture(const char* account,unsigned slot,const void* bytes,std::size_t count) noexcept
{
    try
    {
        if(!state_ || !bytes || count<4) return false;
        std::lock_guard<std::mutex> guard(state_->lock);
        auto found=state_->characters.find(key(text(account,20),slot));
        if(found==state_->characters.end() || !state_->ready) return false;
        auto& character=found->second;
        CheckpointWorkerCapture value;
        put(value.character,character.id);value.slot=slot;
        value.generation=character.generation+1;value.session=character.session;
        value.version=character.version;value.revision=character.revision;
        if(!state_->worker.submit(value,bytes,count)) return false;
        // Each finished capture advances the entity version and revision by one.
        character.generation=value.generation;character.last=value.generation;
        character.outstanding.push_back(value.generation);
        ++character.version;++character.revision;
        return true;
    }
    catch(...){return false;}
}
bool AdmissionCoordinator::leave(const char* account,unsigned slot) noexcept
{
    try
    {
        if(!state_) return false;
        State::Job job;job.kind=State::Kind::Leave;job.account=text(account,20);job.slot=slot;
        job.deadline=GetTickCount64()+60000;
        return state_->queue(std::move(job))!=0;
    }
    catch(...){return false;}
}
std::uint64_t AdmissionCoordinator::depart(const char* account,unsigned slot,const char* target) noexcept
{
    try
    {
        if(!state_) return 0;
        State::Job job;job.kind=State::Kind::Depart;job.account=text(account,20);job.slot=slot;job.target=text(target,64);
        if(job.target.empty() || job.target.find_first_not_of("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")!=std::string::npos)
            return 0;
        job.deadline=GetTickCount64()+20000;
        return state_->queue(std::move(job));
    }
    catch(...){return 0;}
}
bool AdmissionCoordinator::poll_departure(std::uint64_t ticket,DepartureResult& result) noexcept
{
    result={};
    try
    {
        if(!state_) {result.state=DepartureState::Refused;return true;}
        std::lock_guard<std::mutex> guard(state_->lock);
        auto found=state_->outcomes.find(ticket);
        if(found==state_->outcomes.end()) return false;
        result=found->second.departure;state_->outcomes.erase(found);return true;
    }
    catch(...){result={};result.state=DepartureState::Refused;return true;}
}
bool AdmissionCoordinator::admitted(const char* account,unsigned slot) noexcept
{
    try
    {
        if(!state_) return false;
        std::lock_guard<std::mutex> guard(state_->lock);
        return state_->characters.count(key(text(account,20),slot))!=0;
    }
    catch(...){return false;}
}
void AdmissionCoordinator::stop() noexcept
{
    if(!state_) return;
    auto state=state_;state_=nullptr;
    try
    {
        {std::lock_guard<std::mutex> guard(state->lock);state->stopping=true;}state->wake.notify_all();
        if(state->thread.joinable()) state->thread.join();
        delete state;
    }
    catch(...){}
}
#else
struct AdmissionCoordinator::State {};
AdmissionCoordinator::~AdmissionCoordinator()=default;
bool AdmissionCoordinator::start(const char*,const char*,const wchar_t*) noexcept{return false;}
CoordinatorStatus AdmissionCoordinator::status() noexcept{return {};}
std::uint64_t AdmissionCoordinator::admit(const char*,unsigned,const void*,std::size_t,const char*) noexcept{return 0;}
bool AdmissionCoordinator::poll_admission(std::uint64_t,AdmissionResult& result,std::vector<unsigned char>& bytes) noexcept
{result={};result.state=AdmissionState::Unavailable;bytes.clear();return true;}
bool AdmissionCoordinator::capture(const char*,unsigned,const void*,std::size_t) noexcept{return false;}
bool AdmissionCoordinator::leave(const char*,unsigned) noexcept{return false;}
std::uint64_t AdmissionCoordinator::depart(const char*,unsigned,const char*) noexcept{return 0;}
bool AdmissionCoordinator::poll_departure(std::uint64_t,DepartureResult& result) noexcept{result={};result.state=DepartureState::Refused;return true;}
bool AdmissionCoordinator::admitted(const char*,unsigned) noexcept{return false;}
void AdmissionCoordinator::stop() noexcept{}
#endif
}
