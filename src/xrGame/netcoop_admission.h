#pragma once
#include <cstddef>
#include <cstdint>
#include <vector>

// M2b native admission coordinator (doc 135): the world master is the primary
// store of player characters. A location server claims its lease, admits a
// player only through the master (create / resume / transfer claim), takes the
// master's durable checkpoint over its local file, mirrors every save and
// closes the session after the last save is durable. No JSON, credentials,
// engine objects or exceptions cross this boundary.
namespace netcoop_world
{
enum class AdmissionState : unsigned { Pending, Admitted, Refused, Unavailable };
struct AdmissionResult
{
    AdmissionState state=AdmissionState::Pending;
    char character[33]{};
    std::uint64_t revision=0;
    bool master_bytes=false; // the bytes are the master's durable checkpoint, newer than the local file
    char reason[160]{};
};
enum class DepartureState : unsigned { Pending, Ready, Refused };
struct DepartureResult
{
    DepartureState state=DepartureState::Pending;
    char token[2049]{};
    char reason[160]{};
};
struct CoordinatorStatus
{
    bool started=false,ready=false,failed=false;
    std::uint64_t epoch=0,fence=0;
    unsigned characters=0,pending=0;
};

// start/stop: simulation thread. The other calls only queue work or read a
// result; all HTTP and filesystem IO runs on the coordinator's own threads.
class AdmissionCoordinator
{
    struct State;
    State* state_=nullptr;
public:
    AdmissionCoordinator() noexcept=default;
    ~AdmissionCoordinator();
    AdmissionCoordinator(const AdmissionCoordinator&)=delete;
    AdmissionCoordinator& operator=(const AdmissionCoordinator&)=delete;
    // Asynchronous: claims the location lease, adopts the location's records
    // and starts the checkpoint worker. False: no master writer (local files).
    bool start(const char* config_path,const char* location,const wchar_t* spool_path) noexcept;
    CoordinatorStatus status() noexcept;
    // local: the local character file's bytes (nullptr/0 without one), compared
    // with the master's checkpoint. token: a master transfer token from the
    // source location, or nullptr. 0: refused at once (invalid identity).
    std::uint64_t admit(const char* account,unsigned slot,const void* local,std::size_t local_size,const char* token) noexcept;
    // true once final; bytes receive the master checkpoint when master_bytes.
    bool poll_admission(std::uint64_t ticket,AdmissionResult& result,std::vector<unsigned char>& bytes) noexcept;
    // Mirrors one complete local snapshot (NCH bytes) of an admitted character.
    bool capture(const char* account,unsigned slot,const void* bytes,std::size_t count) noexcept;
    // The player left: the session closes after the last capture is durable.
    bool leave(const char* account,unsigned slot) noexcept;
    // Level changer: after the last capture is durable the master freezes the
    // character for the target location and returns its transfer token.
    std::uint64_t depart(const char* account,unsigned slot,const char* target) noexcept;
    bool poll_departure(std::uint64_t ticket,DepartureResult& result) noexcept;
    bool admitted(const char* account,unsigned slot) noexcept;
    void stop() noexcept;
};
}
