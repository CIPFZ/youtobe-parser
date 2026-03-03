#include "api_server.h"
#include "asr_worker.h"
#include "merge_worker.h"
#include "audio_convert_worker.h"
#include "subtitle_embed_worker.h"
#include "compose_worker.h"
#include "task_manager.h"

#include <cstdlib>
#include <iostream>
#include <string>

int main() {
    const char* db_path_env = std::getenv("AV_TASK_DB_PATH");
    const std::string db_path = (db_path_env != nullptr && db_path_env[0] != '\0') ? db_path_env : "task_manager.db";
    avsvc::TaskManager manager(db_path);
    avsvc::MergeWorker worker;
    avsvc::AsrWorker asr_worker;
    avsvc::AudioConvertWorker audio_convert_worker;
    avsvc::SubtitleEmbedWorker subtitle_embed_worker;
    avsvc::ComposeWorker compose_worker;
    avsvc::ApiServer server(manager, worker, asr_worker, audio_convert_worker, subtitle_embed_worker, compose_worker);

#ifdef HAVE_WORKFLOW
    std::cout << "av_service starting on 0.0.0.0:8888\n";
    return server.start(8888);
#else
    std::cout << "workflow headers not detected; cannot start HTTP service in this environment\n";
    std::cout << "Please install sogou/workflow dev headers and rebuild.\n";
    return 1;
#endif
}
