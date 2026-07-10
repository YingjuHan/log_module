#include "cae_logger.h"

#include <chrono>
#include <cstdint>
#include <exception>
#include <string>
#include <stdexcept>
#include <thread>

namespace {

void tiny_work(std::uint64_t milliseconds = 2) {
    std::this_thread::sleep_for(std::chrono::milliseconds(milliseconds));
}

void emit_minimal_example() {
    CAE_LOG(Info).module("System")
        .message("CAE application started.")
        .submit();
}

void emit_builder_examples(const std::string& case_id) {
    CAE_LOG(Info)
        .module("System")
        .stage("Workflow")
        .action("application_start")
        .result("started")
        .object("case", case_id.c_str())
        .message("CAE application started.")
        .submit();

    CAE_LOG(Info)
        .module("Geometry")
        .stage("Geometry")
        .action("import_body")
        .object("file", "case_geometry.step")
        .result("completed")
        .metric("bodies", static_cast<std::int64_t>(18))
        .metric("faces", static_cast<std::int64_t>(2456))
        .metric("geometry_unit_scale", 0.001)
        .message("Geometry import completed.")
        .submit();

    CAE_LOG(Warn)
        .module("Mesh")
        .stage("Mesh")
        .action("quality_gate")
        .object("region", "region_03")
        .result("degraded")
        .reason("mesh_quality_failed")
        .metric("max_skewness", 0.94)
        .metric("negative_volume_cells", static_cast<std::int64_t>(0))
        .message("Mesh quality gate degraded; local remesh requested.")
        .submit();

    CAE_LOG(Info)
        .module("Solver")
        .stage("Iteration")
        .action("nonlinear_step")
        .result("completed")
        .metric("iteration", static_cast<std::int64_t>(42))
        .metric("residual", 1.2e-4)
        .metric("courant", 0.81)
        .metric("converged", false)
        .message("Nonlinear iteration completed.")
        .submit();

    CAE_LOG(Error)
        .module("PostProcess.Output")
        .stage("Output")
        .action("export")
        .object("file", "stress_summary.csv")
        .result("failed")
        .reason("disk_full")
        .message("Export failed. Please check available disk space.")
        .submit();
}

void emit_text_macro_examples() {
    CAE_LOG(Trace).module("Mesh")
        .message("Visiting cell {}", 7)
        .submit();
    CAE_LOG(Debug).module("Geometry")
        .message("Detected {} candidate sliver faces.", 3)
        .submit();
    CAE_LOG(Info).module("System")
        .message("Workflow started for case {}.", "Case_001")
        .submit();
    CAE_LOG(Warn).module("PostProcess.Reader")
        .message("Optional field {} is missing.", "Temperature")
        .submit();
    CAE_LOG(Error).module("PostProcess.Output")
        .message("Failed to open output file {}.", "result.csv")
        .submit();
    CAE_LOG(Critical).module("Solver")
        .message("Result database is corrupted; solver will abort.")
        .submit();
}

void emit_duration_examples() {
    const auto t0 = std::chrono::steady_clock::now();
    tiny_work();
    const auto elapsed = std::chrono::duration_cast<std::chrono::microseconds>(
        std::chrono::steady_clock::now() - t0).count();
    const auto duration_us = elapsed > 0 ? static_cast<std::uint64_t>(elapsed) : 1;

    CAE_LOG_INFO_DUR("Mesh", duration_us)
        .message("Volume mesh completed.")
        .submit();
    CAE_LOG_WARN_DUR("Solver", duration_us)
        .message("Time step completed with residual plateau.")
        .submit();
    CAE_LOG_ERROR_DUR("PostProcess.Output", duration_us)
        .message("Export failed after retry.")
        .submit();
}

void emit_scope_examples() {
    {
        CAE_LOG_SCOPE(Info)
            .module("Mesh")
            .message("Volume mesh generation completed.")
            .submit();
        tiny_work();
    }

    {
        CAE_LOG_SCOPE(Info)
            .module("Geometry")
            .message("{} healing completed.", "Geometry")
            .submit();
        tiny_work();
    }

    {
        cae::ScopedTimer timer("PostProcess.Reader", cae::Level::Info, "Reader open scope completed.");
        timer.submit();
        tiny_work();
    }
}

void emit_task_scope_examples() {
    {
        CAE_SCOPE_TASK(Info, "System", "Workflow", std::string("full_pipeline"));
        tiny_work();

        CAE_LOG(Info)
            .module("System")
            .stage("Workflow")
            .action("case_open")
            .object("case", "Case_001")
            .result("started")
            .message("Case workflow started.")
            .submit();
    }

    {
        cae::TaskScope scope("PostProcess.Output", "Output", cae::Level::Info, "export");
        tiny_work();

        CAE_LOG(Info)
            .module("PostProcess.Output")
            .stage("Output")
            .action("export")
            .object("file", "result.vtu")
            .result("completed")
            .metric("export_bytes", static_cast<std::int64_t>(4096))
            .message("Result export completed.")
            .submit();
    }

    {
        cae::TaskScope scope("Mesh", "Mesh", cae::Level::Info, "volume_mesh");
        tiny_work();
        scope.cancel();

        CAE_LOG(Warn)
            .module("Mesh")
            .stage("Mesh")
            .action("volume_mesh")
            .result("cancelled")
            .reason("user_cancelled")
            .message("Volume mesh generation cancelled by user.")
            .submit();
    }

    {
        cae::TaskScope scope("Solver", "Iteration", cae::Level::Info, "nonlinear_loop");
        try {
            tiny_work();
            throw std::runtime_error("synthetic solver failure");
        } catch (const std::exception&) {
            scope.cancel();

            CAE_LOG(Error)
                .module("Solver")
                .stage("Iteration")
                .action("nonlinear_loop")
                .result("failed")
                .reason("non_convergence")
                .message("Solver nonlinear loop failed.")
                .submit();
        }
    }
}

void emit_cross_thread_trace_example() {
    CAE_SCOPE_TASK(Info, "System", "Workflow", std::string("threaded_pipeline"));
    const std::string trace_id = cae::get_trace_id();

    std::thread worker([trace_id]() {
        cae::set_thread_name("SolverWorker");
        cae::set_node_id("node-worker");
        cae::set_mpi_rank(1);

        CAE_SCOPE_TASK(
            Info,
            "Solver",
            "Iteration",
            std::string("nonlinear_loop"),
            trace_id);

        CAE_LOG(Info)
            .module("Solver")
            .stage("Iteration")
            .action("convergence_summary")
            .result("completed")
            .metric("iteration", static_cast<std::int64_t>(8))
            .metric("final_residual", 9.5e-5)
            .metric("converged", true)
            .message("Solver converged.")
            .submit();
    });

    worker.join();
}

} // namespace

int main(int argc, char* argv[]) {
    const std::string session = argc > 1 ? argv[1] : "DocCase_1";

    cae::LoggerOptions options;
    options.thread_model = cae::ThreadModel::MultiThread;
    options.process_model = cae::ProcessModel::MultiProcess;
    options.io_mode = cae::IOMode::Async;
    options.enable_console = false;
    options.enable_text_log = true;
    options.enable_analysis_log = true;
    options.truncate_file = false;
    options.min_level = cae::Level::Trace;
    options.flush_level = cae::Level::Error;
    options.log_dir = "logs";
    options.analysis_log_name = "cae_events.jsonl";
    options.enable_call_chain_analysis = true;
    options.call_chain_min_level = cae::Level::Error;
    options.call_chain_max_depth = 16;
    options.call_chain_skip = 0;

    cae::init(options);
    cae::set_session(session);
    cae::set_thread_name("MainThread");
    cae::set_node_id("node-main");
    cae::set_mpi_rank(0);

    emit_minimal_example();
    emit_builder_examples(session);
    emit_text_macro_examples();
    emit_duration_examples();
    emit_scope_examples();
    emit_task_scope_examples();
    emit_cross_thread_trace_example();

    CAE_LOG(Info)
        .module("System")
        .stage("Workflow")
        .action("application_shutdown")
        .result("completed")
        .message("CAE application shutdown completed.")
        .submit();

    cae::shutdown();
    return 0;
}
