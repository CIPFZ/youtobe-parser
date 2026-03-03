#include "task_manager.h"

#include <atomic>
#include <cstdint>
#include <sstream>
#include <stdexcept>

#include <sqlite3.h>

namespace avsvc {

namespace {
std::atomic<uint64_t> g_seq{0};

class Statement {
public:
    Statement(sqlite3* db, const char* sql) {
        if (sqlite3_prepare_v2(db, sql, -1, &stmt_, nullptr) != SQLITE_OK) {
            throw std::runtime_error(sqlite3_errmsg(db));
        }
    }

    ~Statement() {
        if (stmt_ != nullptr) {
            sqlite3_finalize(stmt_);
        }
    }

    sqlite3_stmt* get() const { return stmt_; }

private:
    sqlite3_stmt* stmt_{nullptr};
};

std::chrono::system_clock::time_point from_ms(int64_t ms) {
    return std::chrono::system_clock::time_point(std::chrono::milliseconds(ms));
}
}  // namespace

TaskManager::TaskManager(const std::string& db_path) {
    if (sqlite3_open(db_path.c_str(), &db_) != SQLITE_OK) {
        const std::string err = db_ != nullptr ? sqlite3_errmsg(db_) : "failed to open sqlite db";
        if (db_ != nullptr) {
            sqlite3_close(db_);
            db_ = nullptr;
        }
        throw std::runtime_error(err);
    }
    init_schema();
}

TaskManager::~TaskManager() {
    std::lock_guard<std::mutex> lk(mu_);
    if (db_ != nullptr) {
        sqlite3_close(db_);
        db_ = nullptr;
    }
}

void TaskManager::init_schema() {
    const char* sql =
        "CREATE TABLE IF NOT EXISTS tasks ("
        "task_id TEXT PRIMARY KEY,"
        "fingerprint TEXT UNIQUE NOT NULL,"
        "video_path TEXT NOT NULL,"
        "audio_path TEXT NOT NULL,"
        "output_path TEXT NOT NULL,"
        "status INTEGER NOT NULL,"
        "progress INTEGER NOT NULL,"
        "message TEXT NOT NULL,"
        "created_at_ms INTEGER NOT NULL,"
        "updated_at_ms INTEGER NOT NULL"
        ");";

    char* err_msg = nullptr;
    if (sqlite3_exec(db_, sql, nullptr, nullptr, &err_msg) != SQLITE_OK) {
        const std::string err = err_msg != nullptr ? err_msg : "failed to init schema";
        sqlite3_free(err_msg);
        throw std::runtime_error(err);
    }
}

int64_t TaskManager::now_ms() {
    return std::chrono::duration_cast<std::chrono::milliseconds>(
               std::chrono::system_clock::now().time_since_epoch())
        .count();
}

std::string TaskManager::now_id() {
    std::ostringstream oss;
    oss << "task_" << now_ms() << "_" << g_seq.fetch_add(1);
    return oss.str();
}

std::string TaskManager::create_or_reuse(const std::string& fingerprint,
                                         const std::string& video_path,
                                         const std::string& audio_path,
                                         const std::string& output_path,
                                         bool* reused) {
    std::lock_guard<std::mutex> lk(mu_);

    {
        Statement query(db_, "SELECT task_id FROM tasks WHERE fingerprint = ?1 LIMIT 1;");
        sqlite3_bind_text(query.get(), 1, fingerprint.c_str(), -1, SQLITE_TRANSIENT);
        if (sqlite3_step(query.get()) == SQLITE_ROW) {
            if (reused != nullptr) {
                *reused = true;
            }
            const unsigned char* tid = sqlite3_column_text(query.get(), 0);
            return tid != nullptr ? reinterpret_cast<const char*>(tid) : "";
        }
    }

    const std::string task_id = now_id();
    const int64_t ts = now_ms();

    Statement insert(db_,
                     "INSERT INTO tasks(task_id, fingerprint, video_path, audio_path, output_path, status, progress, "
                     "message, created_at_ms, updated_at_ms) "
                     "VALUES(?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10);");

    sqlite3_bind_text(insert.get(), 1, task_id.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(insert.get(), 2, fingerprint.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(insert.get(), 3, video_path.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(insert.get(), 4, audio_path.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(insert.get(), 5, output_path.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_int(insert.get(), 6, static_cast<int>(TaskStatus::Pending));
    sqlite3_bind_int(insert.get(), 7, 0);
    sqlite3_bind_text(insert.get(), 8, "queued", -1, SQLITE_STATIC);
    sqlite3_bind_int64(insert.get(), 9, ts);
    sqlite3_bind_int64(insert.get(), 10, ts);

    if (sqlite3_step(insert.get()) != SQLITE_DONE) {
        throw std::runtime_error(sqlite3_errmsg(db_));
    }

    if (reused != nullptr) {
        *reused = false;
    }
    return task_id;
}

TaskStatus TaskManager::status_from_int(int value) {
    switch (value) {
        case static_cast<int>(TaskStatus::Pending):
            return TaskStatus::Pending;
        case static_cast<int>(TaskStatus::Running):
            return TaskStatus::Running;
        case static_cast<int>(TaskStatus::Success):
            return TaskStatus::Success;
        case static_cast<int>(TaskStatus::Failed):
            return TaskStatus::Failed;
        case static_cast<int>(TaskStatus::Canceled):
            return TaskStatus::Canceled;
        default:
            return TaskStatus::Failed;
    }
}

std::optional<TaskRecord> TaskManager::get_task(const std::string& task_id) const {
    std::lock_guard<std::mutex> lk(mu_);

    Statement query(db_,
                    "SELECT task_id, fingerprint, video_path, audio_path, output_path, status, progress, message, "
                    "created_at_ms, updated_at_ms "
                    "FROM tasks WHERE task_id = ?1 LIMIT 1;");
    sqlite3_bind_text(query.get(), 1, task_id.c_str(), -1, SQLITE_TRANSIENT);

    if (sqlite3_step(query.get()) != SQLITE_ROW) {
        return std::nullopt;
    }

    TaskRecord rec;
    rec.task_id = reinterpret_cast<const char*>(sqlite3_column_text(query.get(), 0));
    rec.fingerprint = reinterpret_cast<const char*>(sqlite3_column_text(query.get(), 1));
    rec.video_path = reinterpret_cast<const char*>(sqlite3_column_text(query.get(), 2));
    rec.audio_path = reinterpret_cast<const char*>(sqlite3_column_text(query.get(), 3));
    rec.output_path = reinterpret_cast<const char*>(sqlite3_column_text(query.get(), 4));
    rec.status = status_from_int(sqlite3_column_int(query.get(), 5));
    rec.progress = sqlite3_column_int(query.get(), 6);
    rec.message = reinterpret_cast<const char*>(sqlite3_column_text(query.get(), 7));
    rec.created_at = from_ms(sqlite3_column_int64(query.get(), 8));
    rec.updated_at = from_ms(sqlite3_column_int64(query.get(), 9));
    return rec;
}

void TaskManager::update_status(const std::string& task_id,
                                TaskStatus status,
                                int progress,
                                const std::string& message) {
    std::lock_guard<std::mutex> lk(mu_);

    Statement update(db_, "UPDATE tasks SET status = ?1, progress = ?2, message = ?3, updated_at_ms = ?4 WHERE task_id = ?5;");
    sqlite3_bind_int(update.get(), 1, static_cast<int>(status));
    sqlite3_bind_int(update.get(), 2, progress);
    sqlite3_bind_text(update.get(), 3, message.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_int64(update.get(), 4, now_ms());
    sqlite3_bind_text(update.get(), 5, task_id.c_str(), -1, SQLITE_TRANSIENT);

    if (sqlite3_step(update.get()) != SQLITE_DONE) {
        throw std::runtime_error(sqlite3_errmsg(db_));
    }
}

std::string to_string(TaskStatus status) {
    switch (status) {
        case TaskStatus::Pending:
            return "PENDING";
        case TaskStatus::Running:
            return "RUNNING";
        case TaskStatus::Success:
            return "SUCCESS";
        case TaskStatus::Failed:
            return "FAILED";
        case TaskStatus::Canceled:
            return "CANCELED";
    }
    return "UNKNOWN";
}

}  // namespace avsvc
