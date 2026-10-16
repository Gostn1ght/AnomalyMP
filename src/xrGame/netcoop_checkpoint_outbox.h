#pragma once

// Private to an exception-enabled IO worker. No engine/Lua pointers, no
// admission or primary-store activation. The caller owns capture generations
// and must coordinate entity versions with inventory/world mutations.
#include "netcoop_player_checkpoint.h"
#include <map>
#include <memory>
#include <set>

namespace netcoop_world
{
#ifdef _WIN32
constexpr std::size_t outbox_jobs=32, outbox_bytes=64*1024*1024;
constexpr std::size_t outbox_history=5120, outbox_index_limit=1024*1024;

struct CheckpointCapture
{
    std::string character;
    std::uint64_t generation=0,fence=0,session=0,version=0,revision=0;
    unsigned slot=0;
};

class CheckpointOutbox
{
    struct Handle
    {
        HANDLE value=INVALID_HANDLE_VALUE;
        Handle()=default;
        explicit Handle(HANDLE h):value(h){}
        ~Handle(){if(value!=INVALID_HANDLE_VALUE) CloseHandle(value);}
        Handle(const Handle&)=delete;
        Handle& operator=(const Handle&)=delete;
    };
    std::wstring root_;
    Handle directory_,lock_;
    BridgeJson binding_,index_;
    std::map<std::string,std::unique_ptr<CheckpointUpload>> clients_;

    std::wstring path(const wchar_t* name) const { return root_+L"\\"+name; }
    std::wstring snapshot_path(const std::string& transaction) const
    {
        if(!checkpoint_hex(transaction,32)) throw std::invalid_argument("outbox transaction");
        return path((L"snapshot-"+std::wstring(transaction.begin(),transaction.end())+L".nch").c_str());
    }
    static std::uint64_t file_size(HANDLE h,std::uint64_t limit)
    {
        BY_HANDLE_FILE_INFORMATION info{};
        if(h==INVALID_HANDLE_VALUE || !GetFileInformationByHandle(h,&info)) throw std::runtime_error("outbox file unavailable");
        const auto size=(std::uint64_t(info.nFileSizeHigh)<<32)|info.nFileSizeLow;
        if((info.dwFileAttributes&(FILE_ATTRIBUTE_REPARSE_POINT|FILE_ATTRIBUTE_DIRECTORY)) || info.nNumberOfLinks!=1 || size>limit)
            throw std::invalid_argument("outbox file identity or budget");
        return size;
    }
    static bool exists(const std::wstring& name)
    {
        if(GetFileAttributesW(name.c_str())!=INVALID_FILE_ATTRIBUTES) return true;
        if(GetLastError()!=ERROR_FILE_NOT_FOUND) throw std::runtime_error("outbox file status");
        return false;
    }
    static std::string read(const std::wstring& name,std::size_t limit)
    {
        Handle file(CreateFileW(name.c_str(),GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_FLAG_OPEN_REPARSE_POINT,nullptr));
        const auto size=file_size(file.value,limit);
        std::string result(std::size_t(size),'\0');
        DWORD got=0;
        if(size && (!ReadFile(file.value,&result[0],DWORD(size),&got,nullptr) || got!=size))
            throw std::runtime_error("outbox short read");
        return result;
    }
    static bool write(HANDLE file,const std::string& bytes)
    {
        std::size_t offset=0;
        while(offset<bytes.size())
        {
            DWORD written=0;
            if(!WriteFile(file,bytes.data()+offset,DWORD(bytes.size()-offset),&written,nullptr) || !written) return false;
            offset+=written;
        }
        return FlushFileBuffers(file)!=FALSE;
    }
    bool save(const BridgeJson& value)
    {
        const auto bytes=value.dump();
        if(bytes.size()>outbox_index_limit) throw std::invalid_argument("outbox index budget");
        const auto next=path(L"outbox.next");
        {
            // Inspect before truncation: never follow a reparse point or write
            // through a hardlink even if an earlier process left this file.
            Handle file(CreateFileW(next.c_str(),GENERIC_READ|GENERIC_WRITE,0,nullptr,OPEN_ALWAYS,
                FILE_FLAG_OPEN_REPARSE_POINT|FILE_FLAG_WRITE_THROUGH,nullptr));
            if(file.value==INVALID_HANDLE_VALUE) return false;
            file_size(file.value,outbox_index_limit);
            LARGE_INTEGER zero{};
            if(!SetFilePointerEx(file.value,zero,nullptr,FILE_BEGIN) || !SetEndOfFile(file.value) || !write(file.value,bytes)) return false;
        }
        return MoveFileExW(next.c_str(),path(L"outbox.json").c_str(),MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH)!=FALSE;
    }
    static BridgeJson binding(const WriterConfig& config,const std::string& instance,std::uint64_t epoch)
    {
        // Validate even when a caller constructed WriterConfig directly.
        WriterConfig::parse(BridgeJson{{"schema",1},{"mode","writer"},{"host","127.0.0.1"},{"port",config.port},
            {"token",config.token},{"actor",config.actor},{"location",config.location},
            {"master_world_id",config.world},{"master_world_seed",config.seed}}.dump(),config.location);
        if(!checkpoint_hex(instance,32) || !epoch || epoch>0x7fffffffffffffffULL)
            throw std::invalid_argument("outbox authority identity");
        return {{"world",config.world},{"seed",config.seed},{"epoch",epoch},{"instance",instance},{"location",config.location}};
    }
    static std::string transaction()
    {
        unsigned char bytes[16]{};
        if(BCryptGenRandom(nullptr,bytes,sizeof(bytes),BCRYPT_USE_SYSTEM_PREFERRED_RNG)<0)
            throw std::runtime_error("outbox transaction unavailable");
        return checkpoint_hex_bytes(std::string(reinterpret_cast<const char*>(bytes),sizeof(bytes)));
    }
    static CheckpointCapture capture(const BridgeJson& job)
    {
        CheckpointCapture result;
        result.character=bridge_identifier(job,"character_id",true);
        result.generation=bridge_unsigned(job,"generation");
        result.fence=bridge_unsigned(job,"fence");result.session=bridge_unsigned(job,"session_fence");
        result.version=bridge_unsigned(job,"entity_version");result.revision=bridge_unsigned(job,"base_revision");
        const auto slot=bridge_unsigned(job,"slot");
        if(!result.generation || result.generation>0x7fffffffffffffffULL || slot<1 || slot>10)
            throw std::invalid_argument("outbox capture generation or slot");
        result.slot=unsigned(slot);return result;
    }
    static void follows(const CheckpointCapture& next,const CheckpointCapture& previous)
    {
        if(next.generation<=previous.generation || next.fence!=previous.fence || next.session!=previous.session ||
            next.slot!=previous.slot || next.version!=previous.version+1 || next.revision!=previous.revision+1)
            throw std::invalid_argument("outbox character ordering changed");
    }
    std::size_t first(const std::string& character) const
    {
        const auto& jobs=index_["jobs"];
        for(std::size_t i=0;i<jobs.size();++i) if(jobs[i]["character_id"]==character) return i;
        throw std::out_of_range("outbox character has no pending checkpoint");
    }
    void validate()
    {
        if(!index_.is_object() || index_.size()!=4 || bridge_unsigned(index_,"schema")!=1 || index_["binding"]!=binding_ ||
            !index_["history"].is_object() || index_["history"].size()>outbox_history ||
            !index_["jobs"].is_array() || index_["jobs"].size()>outbox_jobs)
            throw std::invalid_argument("outbox schema or authority changed");
        for(auto it=index_["history"].begin();it!=index_["history"].end();++it)
            if(!checkpoint_hex(it.key(),32) || !bridge_unsigned(index_["history"],it.key().c_str()) ||
                bridge_unsigned(index_["history"],it.key().c_str())>0x7fffffffffffffffULL)
                throw std::invalid_argument("outbox history invalid");
        std::map<std::string,CheckpointCapture> previous;
        std::size_t total=0;
        for(const auto& job:index_["jobs"])
        {
            if(!job.is_object() || job.size()!=11) throw std::invalid_argument("outbox job schema");
            const auto item=capture(job);
            const auto prior=previous.find(item.character);
            if(prior!=previous.end()) follows(item,prior->second);
            previous[item.character]=item;
            const auto tx=bridge_identifier(job,"transaction",true);
            const auto size=bridge_unsigned(job,"bytes");
            if(size<4 || size>checkpoint_limit || total>outbox_bytes-size || clients_.count(tx))
                throw std::invalid_argument("outbox snapshot budget or duplicate");
            total+=std::size_t(size);
            auto raw=read(snapshot_path(tx),checkpoint_limit);
            if(raw.size()!=size || !job.contains("sha256") || job["sha256"]!=checkpoint_sha256(raw))
                throw std::invalid_argument("outbox snapshot checksum");
            auto client=std::make_unique<CheckpointUpload>(std::move(raw),item.character,item.fence,item.session,
                item.version,item.revision,item.slot,tx);
            client->restore_cursor(job.at("cursor"));
            clients_.emplace(tx,std::move(client));
        }
        for(const auto& item:previous)
            if(bridge_unsigned(index_["history"],item.first.c_str())!=item.second.generation)
                throw std::invalid_argument("outbox generation highwater changed");
    }
    bool cleanup(bool has_index=true)
    {
        std::set<std::wstring> retained;
        for(const auto& job:index_["jobs"])
        {
            const auto tx=job["transaction"].get<std::string>();
            retained.insert(L"snapshot-"+std::wstring(tx.begin(),tx.end())+L".nch");
        }
        // Only queue-owned names in this dedicated directory may be removed.
        // Validate the entire bounded inventory before deleting anything.
        std::vector<std::wstring> stale;
        WIN32_FIND_DATAW item{};
        HANDLE search=FindFirstFileW(path(L"*").c_str(),&item);
        if(search==INVALID_HANDLE_VALUE) throw std::runtime_error("outbox directory unavailable");
        struct Search {HANDLE value;~Search(){FindClose(value);}} guard{search};
        std::size_t count=0;
        do
        {
            const std::wstring name=item.cFileName;
            if(name==L"." || name==L"..") continue;
            if(++count>outbox_jobs+4 || (item.dwFileAttributes&(FILE_ATTRIBUTE_DIRECTORY|FILE_ATTRIBUTE_REPARSE_POINT)))
                throw std::invalid_argument("outbox directory contents changed");
            if(name==L"outbox.lock" || name==L"outbox.json") continue;
            if(name!=L"outbox.next")
            {
                if(name.size()!=45 || name.compare(0,9,L"snapshot-") || name.compare(41,4,L".nch") ||
                    name.substr(9,32).find_first_not_of(L"0123456789abcdef")!=std::wstring::npos)
                    throw std::invalid_argument("outbox contains an unrelated file");
                if(!has_index) throw std::invalid_argument("outbox index missing beside snapshot");
                if(retained.count(name)) continue;
            }
            Handle file(CreateFileW(path(name.c_str()).c_str(),GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,
                FILE_FLAG_OPEN_REPARSE_POINT,nullptr));
            file_size(file.value,name==L"outbox.next" ? outbox_index_limit:checkpoint_limit);
            stale.push_back(name);
        } while(FindNextFileW(search,&item));
        if(GetLastError()!=ERROR_NO_MORE_FILES) throw std::runtime_error("outbox directory scan failed");
        for(const auto& name:stale) if(!DeleteFileW(path(name.c_str()).c_str())) return false;
        return true;
    }
public:
    CheckpointOutbox(const std::wstring& directory,const WriterConfig& config,const std::string& instance,std::uint64_t epoch)
        :binding_(binding(config,instance,epoch))
    {
        if(directory.size()<4 || directory.size()>2048 || directory[1]!=L':' || directory[2]!=L'\\')
            throw std::invalid_argument("outbox requires a local absolute directory");
        wchar_t absolute[4096]{};
        const auto length=GetFullPathNameW(directory.c_str(),4096,absolute,nullptr);
        if(!length || length>=4096) throw std::invalid_argument("outbox directory path");
        root_=absolute;
        while(root_.size()>3 && root_.back()==L'\\') root_.pop_back();
        if(root_.size()<=3) throw std::invalid_argument("outbox requires a dedicated directory");
        if(!CreateDirectoryW(root_.c_str(),nullptr) && GetLastError()!=ERROR_ALREADY_EXISTS)
            throw std::runtime_error("outbox directory creation failed");
        directory_.value=CreateFileW(root_.c_str(),FILE_READ_ATTRIBUTES,FILE_SHARE_READ|FILE_SHARE_WRITE,nullptr,OPEN_EXISTING,
            FILE_FLAG_BACKUP_SEMANTICS|FILE_FLAG_OPEN_REPARSE_POINT,nullptr);
        BY_HANDLE_FILE_INFORMATION info{};
        if(directory_.value==INVALID_HANDLE_VALUE || !GetFileInformationByHandle(directory_.value,&info) ||
            !(info.dwFileAttributes&FILE_ATTRIBUTE_DIRECTORY) || (info.dwFileAttributes&FILE_ATTRIBUTE_REPARSE_POINT))
            throw std::invalid_argument("outbox directory identity");
        lock_.value=CreateFileW(path(L"outbox.lock").c_str(),GENERIC_READ|GENERIC_WRITE,0,nullptr,OPEN_ALWAYS,
            FILE_FLAG_OPEN_REPARSE_POINT,nullptr);
        file_size(lock_.value,0);
        const auto filename=path(L"outbox.json");
        const bool has_index=exists(filename);
        if(has_index) index_=bridge_json(read(filename,outbox_index_limit),outbox_index_limit);
        else index_={{"schema",1},{"binding",binding_},{"history",BridgeJson::object()},{"jobs",BridgeJson::array()}};
        validate(); // Corruption/scope mismatch leaves every queued file intact.
        if(!cleanup(has_index)) throw std::runtime_error("outbox stale cleanup failed");
        if(!has_index && !save(index_)) throw std::runtime_error("outbox initialization failed");
    }
    CheckpointOutbox(const CheckpointOutbox&)=delete;
    CheckpointOutbox& operator=(const CheckpointOutbox&)=delete;

    // IO worker only: true means snapshot/index are durable locally, not on
    // the master. Rejected admission leaves the caller's capture unacknowledged.
    bool enqueue(const CheckpointCapture& item,const std::string& raw)
    {
        if(!checkpoint_hex(item.character,32) || !item.generation || item.generation>0x7fffffffffffffffULL || !checkpoint_format(raw))
            throw std::invalid_argument("outbox capture invalid");
        if(index_["history"].contains(item.character) && item.generation<=bridge_unsigned(index_["history"],item.character.c_str())) return false;
        if(index_["jobs"].size()>=outbox_jobs || (!index_["history"].contains(item.character) && index_["history"].size()>=outbox_history)) return false;
        std::size_t used=0;
        const BridgeJson* previous=nullptr;
        for(const auto& job:index_["jobs"])
        {
            used+=std::size_t(bridge_unsigned(job,"bytes"));
            if(job["character_id"]==item.character) previous=&job;
        }
        if(previous) follows(item,capture(*previous));
        if(raw.size()>outbox_bytes-used || !cleanup()) return false;
        const auto tx=transaction();
        auto client=std::make_unique<CheckpointUpload>(raw,item.character,item.fence,item.session,item.version,item.revision,item.slot,tx);
        BridgeJson proposed=index_;
        proposed["history"][item.character]=item.generation;
        proposed["jobs"].push_back({{"character_id",item.character},{"generation",item.generation},{"fence",item.fence},
            {"session_fence",item.session},{"entity_version",item.version},{"base_revision",item.revision},{"slot",item.slot},
            {"transaction",tx},{"sha256",checkpoint_sha256(raw)},{"bytes",raw.size()},{"cursor",client->cursor()}});
        const auto snapshot=snapshot_path(tx);
        bool written=false;
        {
            Handle file(CreateFileW(snapshot.c_str(),GENERIC_WRITE,0,nullptr,CREATE_NEW,
                FILE_FLAG_WRITE_THROUGH|FILE_FLAG_OPEN_REPARSE_POINT,nullptr));
            if(file.value==INVALID_HANDLE_VALUE) return false;
            written=write(file.value,raw);
        }
        if(!written) { DeleteFileW(snapshot.c_str());return false; }
        // Allocate before publishing the index; successful publication is
        // followed only by non-throwing swaps/ownership changes.
        try
        {
            clients_.emplace(tx,std::move(client));
            if(save(proposed)) { index_.swap(proposed);return true; }
        }
        catch(...) { clients_.erase(tx);DeleteFileW(snapshot.c_str());throw; }
        clients_.erase(tx);DeleteFileW(snapshot.c_str());return false;
    }
    std::vector<std::string> pending() const
    {
        std::vector<std::string> result;
        std::set<std::string> seen;
        for(const auto& job:index_["jobs"])
        {
            const auto character=job["character_id"].get<std::string>();
            if(seen.insert(character).second) result.push_back(character);
        }
        return result;
    }
    std::uint64_t accepted_generation(const std::string& character) const
    {
        if(!checkpoint_hex(character,32)) throw std::invalid_argument("outbox character identity");
        return index_["history"].contains(character) ? bridge_unsigned(index_["history"],character.c_str()):0;
    }
    CheckpointStep advance(const std::string& character,const CheckpointRequest& request)
    {
        const auto position=first(character);
        const auto tx=index_["jobs"][position]["transaction"].get<std::string>();
        auto& client=*clients_.at(tx);
        const auto old=index_["jobs"][position]["cursor"];
        BridgeJson proposed=index_;
        try
        {
            const auto result=client.step(request);
            if(result==CheckpointStep::Retry || result==CheckpointStep::Rejected) return result;
            proposed["jobs"][position]["cursor"]=client.cursor();
            if(!save(proposed)) { client.restore_cursor(old);return CheckpointStep::Retry; }
            index_.swap(proposed);return result;
        }
        catch(...) { client.restore_cursor(old);throw; }
    }
    // A recovered disk cursor never exposes a receipt until Finish has been
    // replayed successfully under the caller's CURRENT fenced HTTP authority.
    BridgeJson completion(const std::string& character) const
    {
        const auto& job=index_["jobs"][first(character)];
        const auto tx=job["transaction"].get<std::string>();
        // This compares admitted generations only. A gameplay coordinator
        // must ALSO compare its newest captured generation before handoff.
        return {{"generation",job["generation"]},{"latest_accepted",index_["history"][character]==job["generation"]},
            {"result",clients_.at(tx)->durable()}};
    }
    // Retire only after the coordinator consumes this exact receipt. Pending
    // newer generations still block a latest-generation handoff barrier.
    bool retire(const std::string& character,std::uint64_t generation)
    {
        const auto position=first(character);
        const auto& job=index_["jobs"][position];
        if(job["generation"]!=generation) return false;
        const auto tx=job["transaction"].get<std::string>();
        clients_.at(tx)->durable();
        BridgeJson proposed=index_;
        proposed["jobs"].erase(proposed["jobs"].begin()+std::ptrdiff_t(position));
        if(!save(proposed)) return false;
        index_.swap(proposed);clients_.erase(tx);
        // An interrupted/unavailable deletion is an unreferenced queue copy;
        // the next admission/recovery cleans it before accepting more bytes.
        DeleteFileW(snapshot_path(tx).c_str());return true;
    }
};
#endif
}
