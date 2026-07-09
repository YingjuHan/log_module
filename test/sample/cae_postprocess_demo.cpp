#include "cae_logger.h"

#include <atomic>
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <random>
#include <string>
#include <thread>
#include <vector>

// ---------------------------------------------------------------------------
//  Utility: random duration in [0.5, 1.5] seconds (configurable range)
// ---------------------------------------------------------------------------
static double rand_elapsed() {
    thread_local std::mt19937 rng(std::random_device{}());
    std::uniform_real_distribution<double> dist(0.05, 0.35);
    return dist(rng);
}

static std::uint64_t duration_us_from_seconds(double seconds) {
    const auto micros = static_cast<std::uint64_t>(seconds * 1000000.0);
    return micros == 0 ? 1 : micros;
}

// ---------------------------------------------------------------------------
//  Demo: simulate a complete CAE post-processing workflow
// ---------------------------------------------------------------------------

class PostProcessDemo {
public:
    explicit PostProcessDemo(std::string session_id)
        : session_id_(std::move(session_id)) {}

    // ---- 4.1  Import -------------------------------------------------------
    void simulate_import() {
        const char* module = "PostProcess.Import";
        cae::TaskScope import_scope(module, "Import", cae::Level::Info, "import");

        // Reader 1: STEP assembly
        {
            CAE_LOG(Info)
                .module(module)
                .stage("Import")
                .action("reader_created")
                .object("reader", "STEP")
                .message("Reader created for \"assembly.stp\".")
                .submit();
            double elapsed = rand_elapsed();
            std::this_thread::sleep_for(std::chrono::milliseconds(static_cast<int>(elapsed * 1000)));
            int entities = 128 + (std::rand() % 50);
            CAE_LOG_INFO_DUR(module, duration_us_from_seconds(elapsed))
                .message("Reader [STEP] opened \"assembly.stp\" entities={} elapsed={:.2f}s", entities, elapsed)
                .submit();
            CAE_LOG(Info)
                .module(module)
                .stage("Import")
                .action("mesh_summary")
                .event_type(cae::EventType::PostProcess)
                .phase(cae::EventPhase::Progress)
                .domain(cae::Domain::Post)
                .entity("reader", "STEP")
                .metric("nodes", static_cast<std::int64_t>(284120))
                .metric("cells", static_cast<std::int64_t>(1513840))
                .metric("blocks", static_cast<std::int64_t>(28))
                .metric("fields", static_cast<std::int64_t>(12))
                .metric("timesteps", static_cast<std::int64_t>(100))
                .message("Imported mesh summary captured.")
                .submit();
        }

        // Reader 2: Ensight case
        {
            auto t0 = std::chrono::steady_clock::now();
            CAE_LOG(Info).module(module)
                .message("Reader [Ensight] created for \"flow.ensi\"")
                .submit();
            double elapsed = rand_elapsed();
            std::this_thread::sleep_for(std::chrono::milliseconds(static_cast<int>(elapsed * 1000)));
            CAE_LOG_INFO_DUR(module, duration_us_from_seconds(elapsed))
                .message("Reader [Ensight] opened \"flow.ensi\" entities=6 elapsed={:.2f}s", elapsed)
                .submit();
            CAE_LOG(Info).module(module)
                .message("Mesh summary: nodes=98240 cells=512000 blocks=6 fields=8 timesteps=200")
                .submit();
        }

        // Reader 3: CSV probe data (triggers a warning)
        {
            auto t0 = std::chrono::steady_clock::now();
            CAE_LOG(Info).module(module)
                .message("Reader [CSV] created for \"probe_data.csv\"")
                .submit();
            double elapsed = rand_elapsed();
            std::this_thread::sleep_for(std::chrono::milliseconds(static_cast<int>(elapsed * 1000)));
            CAE_LOG_WARN_DUR(module, duration_us_from_seconds(elapsed))
                .message("Reader [CSV] opened \"probe_data.csv\" with 2 missing columns (elapsed={:.2f}s)", elapsed)
                .submit();
        }

        // Reader 4: failed case
        {
            CAE_LOG(Error)
                .module(module)
                .stage("Import")
                .action("reader_open")
                .object("reader", "Unknown")
                .result("failed")
                .reason("unsupported_format")
                .message("Reader failed for \"broken_mesh.case\".")
                .submit();
        }
    }

    // ---- 4.2  Pipeline -----------------------------------------------------
    void simulate_pipeline(const std::string& trace_id) {
        const char* module = "PostProcess.Pipeline";
        cae::TaskScope pipeline_scope(module, "Pipeline", cae::Level::Info, "pipeline", trace_id);

        CAE_LOG(Info).module(module)
            .message("Filter [Clip] created <- STEP_Reader:0")
            .submit();
        CAE_LOG(Info).module(module)
            .message("Filter [Contour] created <- Clip:0")
            .submit();
        CAE_LOG(Info).module(module)
            .message("Filter [Slice] created <- Contour:0")
            .submit();

        std::this_thread::sleep_for(std::chrono::milliseconds(50));

        // Property changes
        CAE_LOG(Info).module(module)
            .message("Filter [Clip].ClipType: \"Plane\" -> \"Sphere\"")
            .submit();
        CAE_LOG(Info).module(module)
            .message("Filter [Clip].SphereRadius: \"0.5\" -> \"0.75\"")
            .submit();
        CAE_LOG(Info).module(module)
            .message("Filter [Contour].ContourValues: \"5\" -> \"12\"")
            .submit();

        std::this_thread::sleep_for(std::chrono::milliseconds(30));

        CAE_LOG(Info)
            .module(module)
            .stage("Pipeline")
            .action("apply")
            .event_type(cae::EventType::PostProcess)
            .phase(cae::EventPhase::Progress)
            .domain(cae::Domain::Post)
            .entity("filter", "Clip")
            .object("filter", "Clip")
            .metric("changed_properties", static_cast<std::int64_t>(3))
            .message("Apply [Clip]: 3 properties changed")
            .submit();

        std::this_thread::sleep_for(std::chrono::milliseconds(50));

        // Filter execution
        {
            double elapsed = rand_elapsed();
            std::this_thread::sleep_for(std::chrono::milliseconds(static_cast<int>(elapsed * 1000)));
            CAE_LOG_INFO_DUR(module, duration_us_from_seconds(elapsed))
                .message("Filter [Clip] executed: output=8234 cells elapsed={:.2f}s", elapsed)
                .submit();
        }

        {
            double elapsed = rand_elapsed();
            std::this_thread::sleep_for(std::chrono::milliseconds(static_cast<int>(elapsed * 1000)));
            CAE_LOG_INFO_DUR(module, duration_us_from_seconds(elapsed))
                .message("Filter [Contour] executed: output=45678 cells elapsed={:.2f}s", elapsed)
                .submit();
        }

        CAE_LOG(Info).module(module)
            .message("PostFilter: auto-convert \"PRESSURE\" from Cell to Point")
            .submit();
        CAE_LOG_INFO_DUR(module, duration_us_from_seconds(0.12))
            .message("Filter [Slice] executed: output=1200 cells elapsed=0.12s")
            .submit();

        // Add a problematic filter
        CAE_LOG(Warn).module(module)
            .message("Filter [WarpByVector] skipped: input has no valid normals")
            .submit();

        std::this_thread::sleep_for(std::chrono::milliseconds(30));

        // Cleanup
        CAE_LOG(Info).module(module)
            .message("Filter [Slice] removed (upstream=Contour downstream=none)")
            .submit();
    }

    // ---- 4.3  Display ------------------------------------------------------
    void simulate_display(const std::string& trace_id) {
        const char* module = "PostProcess.Display";
        cae::TaskScope display_scope(module, "Display", cae::Level::Info, "display", trace_id);

        CAE_LOG(Info).module(module)
            .message("Representation[Clip].Visibility: false -> true")
            .submit();
        CAE_LOG(Info).module(module)
            .message("Representation[Clip].Type: \"Surface\" -> \"Wireframe\"")
            .submit();
        CAE_LOG(Info).module(module)
            .message("Representation[Clip].ColorArrayName: \"\" -> \"PRESSURE\"")
            .submit();
        CAE_LOG(Info).module(module)
            .message("Representation[Clip].Component: \"Magnitude\" -> \"X\"")
            .submit();
        CAE_LOG(Info).module(module)
            .message("Representation[Clip].MapScalars: false -> true")
            .submit();

        std::this_thread::sleep_for(std::chrono::milliseconds(30));

        CAE_LOG(Info).module(module)
            .message("Representation[Contour].Visibility: false -> true")
            .submit();
        CAE_LOG(Info).module(module)
            .message("Representation[Contour].Type: \"Surface\" -> \"SurfaceWithEdges\"")
            .submit();
        CAE_LOG(Info)
            .module(module)
            .stage("Display")
            .action("representation_update")
            .object("representation", "Contour")
            .result("applied")
            .message("Display representation updates applied.")
            .submit();
    }

    // ---- 4.4  ColorMap & TransferFunc --------------------------------------
    void simulate_colormap(const std::string& trace_id) {
        cae::TaskScope colormap_scope("PostProcess.ColorMap", "ColorMap", cae::Level::Info, "colormap", trace_id);
        // ColorMap
        CAE_LOG(Info).module("PostProcess.ColorMap")
            .message("LUT created for \"PRESSURE\": range=[1.013e+05,2.027e+05] preset=\"CoolToWarm\"")
            .submit();
        CAE_LOG(Info).module("PostProcess.ColorMap")
            .message("LUT created for \"VELOCITY\": range=[0.000e+00,1.500e+02] preset=\"RainbowUniform\"")
            .submit();

        std::this_thread::sleep_for(std::chrono::milliseconds(30));

        // TransferFunc
        CAE_LOG(Info).module("PostProcess.TransferFunc")
            .message("Rescale LUT [PRESSURE]: [1.013e+05,2.027e+05] -> [0.000e+00,5.000e+05]")
            .submit();
        CAE_LOG(Info).module("PostProcess.TransferFunc")
            .message("Invert LUT [PRESSURE]")
            .submit();
        CAE_LOG(Info).module("PostProcess.TransferFunc")
            .message("LUT [PRESSURE] mapping: Linear -> Log10")
            .submit();
        CAE_LOG(Info).module("PostProcess.TransferFunc")
            .message("Opacity [PRESSURE]: 5 control points")
            .submit();
        CAE_LOG(Info).module("PostProcess.TransferFunc")
            .message("Rescale LUT [VELOCITY]: [0.000e+00,1.500e+02] -> [0.000e+00,2.000e+02]")
            .submit();
        CAE_LOG(Info).module("PostProcess.ColorMap")
            .message("LUT [PRESSURE] preset: \"CoolToWarm\" -> \"Jet\"")
            .submit();
        CAE_LOG(Info)
            .module("PostProcess.TransferFunc")
            .stage("TransferFunc")
            .action("transfer_summary")
            .metric("rescale_operations", static_cast<std::int64_t>(2))
            .metric("opacity_control_points", static_cast<std::int64_t>(5))
            .message("Transfer-function updates completed.")
            .submit();
    }

    // ---- 4.5  Interaction --------------------------------------------------
    void simulate_interaction(const std::string& trace_id) {
        const char* module = "PostProcess.Interaction";
        cae::TaskScope interaction_scope(module, "Interaction", cae::Level::Info, "interaction", trace_id);

        CAE_LOG(Info).module(module)
            .message("View [RenderView1] created: type=3D layout=(0,0)")
            .submit();
        CAE_LOG(Info).module(module)
            .message("View [RenderView2] created: type=3D layout=(1,0)")
            .submit();

        std::this_thread::sleep_for(std::chrono::milliseconds(30));

        CAE_LOG(Info).module(module)
            .message("Time step: index=5 value=0.500")
            .submit();
        CAE_LOG(Info).module(module)
            .message("Interaction mode: \"RubberBandZoom\"")
            .submit();
        CAE_LOG(Info).module(module)
            .message("Annotation[ScalarBar1]: text=\"PRESSURE (MPa)\" position=(0.85,0.10)")
            .submit();
        CAE_LOG(Info).module(module)
            .message("GridAxes[RenderView1]: visibility=true")
            .submit();
        CAE_LOG(Info).module(module)
            .message("Time step: index=12 value=1.200")
            .submit();
        CAE_LOG(Info)
            .module(module)
            .stage("Interaction")
            .action("view_sync")
            .event_type(cae::EventType::UI)
            .phase(cae::EventPhase::Progress)
            .domain(cae::Domain::Post)
            .entity("view", "RenderView")
            .metric("time_step_index", static_cast<std::int64_t>(12))
            .message("Interaction state synchronized across views.")
            .submit();
    }

    // ---- 4.6  Selection ----------------------------------------------------
    void simulate_selection(const std::string& trace_id) {
        const char* module = "PostProcess.Selection";
        cae::TaskScope selection_scope(module, "Selection", cae::Level::Info, "selection", trace_id);

        CAE_LOG(Info).module(module)
            .message("Selection: mode=SurfaceCells elements=1245 type=\"Frustum\"")
            .submit();

        std::this_thread::sleep_for(std::chrono::milliseconds(30));

        CAE_LOG(Info).module(module)
            .message("Selection op: Combine (input=1245 elements)")
            .submit();
        CAE_LOG(Info).module(module)
            .message("Selection op: Toggle (input=89 elements)")
            .submit();

        {
            double elapsed = rand_elapsed();
            std::this_thread::sleep_for(std::chrono::milliseconds(static_cast<int>(elapsed * 1000)));
            CAE_LOG_INFO_DUR(module, duration_us_from_seconds(elapsed))
                .message("Extract selection: output=892 cells elapsed={:.2f}s", elapsed)
                .submit();
        }

        CAE_LOG(Info)
            .module(module)
            .stage("Selection")
            .action("find_data")
            .metric("matches", static_cast<std::int64_t>(456))
            .message("Find data: condition=\"PRESSURE > 1.5e5\" matches=456")
            .submit();
        CAE_LOG(Warn).module(module)
            .message("Selection: threshold mode exceeded maximum elements, clipped to 10000")
            .submit();
    }

    // ---- 4.7  Output -------------------------------------------------------
    void simulate_output() {
        const char* module = "PostProcess.Output";
        cae::TaskScope output_scope(module, "Output", cae::Level::Info, "output");

        // Screenshot
        {
            CAE_LOG(Info).module(module)
                .message("Screenshot: \"stress_plot.png\" (1920x1080@1x) format=PNG transparent=false")
                .submit();
            double elapsed = rand_elapsed();
            std::this_thread::sleep_for(std::chrono::milliseconds(static_cast<int>(elapsed * 1000)));
            CAE_LOG_INFO_DUR(module, duration_us_from_seconds(elapsed))
                .message("Screenshot saved: \"stress_plot.png\" (4.1MB elapsed={:.2f}s)", elapsed)
                .submit();
        }

        // Stereo screenshot
        {
            CAE_LOG(Info).module(module)
                .message("Stereo screenshot: left=\"stress_L.png\" right=\"stress_R.png\" mode=SideBySide")
                .submit();
        }

        // Data export
        {
            CAE_LOG(Info)
                .module(module)
                .stage("Output")
                .action("export_started")
                .object("file", "result.csv")
                .message("Data export: \"result.csv\" format=CSV variables=PRESSURE,VELOCITY,TEMPERATURE")
                .submit();
            double elapsed = rand_elapsed();
            std::this_thread::sleep_for(std::chrono::milliseconds(static_cast<int>(elapsed * 1000)));
            CAE_LOG_INFO_DUR(module, duration_us_from_seconds(elapsed))
                .message("Data exported: \"result.csv\" (12.8MB elapsed={:.2f}s)", elapsed)
                .submit();
        }

        // Export failure
        {
            CAE_LOG(Error)
                .module(module)
                .stage("Output")
                .action("export")
                .object("file", "result_big.plt")
                .result("failed")
                .reason("disk_full")
                .message("Export failed for \"result_big.plt\".")
                .submit();
        }

        // Animation
        {
            CAE_LOG(Info).module(module)
                .message("Animation: 0.000-1.000 frames=30 fps=10 output=\"anim/\"")
                .submit();
            for (int f = 1; f <= 5; ++f) {
                double elapsed = rand_elapsed() * 0.5;
                std::this_thread::sleep_for(std::chrono::milliseconds(static_cast<int>(elapsed * 1000)));
                CAE_LOG_INFO_DUR(module, duration_us_from_seconds(elapsed))
                    .message("Animation frame {}/30 time={:.3f} elapsed={:.2f}s", f, f * 0.034, elapsed)
                    .submit();
            }
            CAE_LOG_INFO_DUR(module, duration_us_from_seconds(13.50))
                .message("Animation saved: \"anim/\" (30 frames avg=0.45s/frame total=13.50s)")
                .submit();
        }
    }

    // ---- 4.8  Summary -----------------------------------------------------
    void simulate_summary(double import_t, double pipeline_t,
                          double display_t, double output_t) {
        const char* module = "PostProcess.Summary";
        cae::TaskScope summary_scope(module, "Summary", cae::Level::Info, "summary");

        CAE_LOG(Info).module(module)
            .message("=== PostProcessing Task Start ===")
            .submit();

        double total = import_t + pipeline_t + display_t + output_t;
        CAE_LOG(Info)
            .module(module)
            .stage("Summary")
            .action("task_summary")
            .event_type(cae::EventType::PostProcess)
            .phase(cae::EventPhase::Progress)
            .domain(cae::Domain::Post)
            .entity("postprocess", "task_summary")
            .metric("import_seconds", import_t)
            .metric("pipeline_seconds", pipeline_t)
            .metric("display_seconds", display_t)
            .metric("output_seconds", output_t)
            .metric("total_seconds", total)
            .message("Task summary generated.")
            .submit();

        CAE_LOG(Info).module(module)
            .message("=== PostProcessing Task End ===")
            .submit();
    }

    void run_all() {
        auto overall_start = std::chrono::steady_clock::now();
        cae::TaskScope workflow_scope("PostProcess", "Workflow", cae::Level::Info, "workflow");
        const std::string workflow_trace_id = cae::get_trace_id();

        // Phase 1: Import (sequential)
        auto t0 = std::chrono::steady_clock::now();
        simulate_import();
        double import_t = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();

        // Phase 2: Pipeline, Display/ColorMap, Interaction/Selection in parallel
        std::atomic<double> pipeline_t{0};
        std::atomic<double> display_t{0};

        std::thread pipeline_thread([&]() {
            cae::set_thread_name("PipelineWorker");
            auto t = std::chrono::steady_clock::now();
            simulate_pipeline(workflow_trace_id);
            pipeline_t = std::chrono::duration<double>(std::chrono::steady_clock::now() - t).count();
        });

        std::thread visual_thread([&]() {
            cae::set_thread_name("VisualWorker");
            auto t = std::chrono::steady_clock::now();
            simulate_display(workflow_trace_id);
            simulate_colormap(workflow_trace_id);
            display_t = std::chrono::duration<double>(std::chrono::steady_clock::now() - t).count();
        });

        std::thread interaction_thread([&]() {
            cae::set_thread_name("InteractionWorker");
            simulate_interaction(workflow_trace_id);
            simulate_selection(workflow_trace_id);
        });

        pipeline_thread.join();
        visual_thread.join();
        interaction_thread.join();

        // Phase 3: Output (sequential)
        auto t_output = std::chrono::steady_clock::now();
        simulate_output();
        double output_t = std::chrono::duration<double>(std::chrono::steady_clock::now() - t_output).count();

        // Phase 4: Summary
        simulate_summary(import_t, pipeline_t.load(), display_t.load(), output_t);

        double total = std::chrono::duration<double>(std::chrono::steady_clock::now() - overall_start).count();
        std::cout << "[" << session_id_ << "] Post-processing demo completed in "
                  << total << "s\n";
    }

private:
    std::string session_id_;
};

// ============================================================================
//  Multi-process entry point
// ============================================================================
int main(int argc, char* argv[]) {
    const char* proc_id = (argc > 1) ? argv[1] : "Proc_1";

    cae::init("cae_logger_config.ini");
    cae::set_session(proc_id);
    cae::set_job_id(std::string("POST_") + proc_id);
    cae::set_node_id("postprocess-node");
    if (std::string(proc_id).rfind("Proc_", 0) == 0) {
        cae::set_mpi_rank(std::stoi(std::string(proc_id).substr(5)) - 1);
    }

    std::cout << "[" << proc_id << "] CAE PostProcess Demo started\n";

    // Main demo: simulate a full post-processing workflow across threads
    PostProcessDemo demo(proc_id);
    demo.run_all();

    cae::shutdown();
    return 0;
}
