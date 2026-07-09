#include "cae_logger.h"

#include <chrono>
#include <cstdint>
#include <string>
#include <thread>

void pause_between_events() {
    std::this_thread::sleep_for(std::chrono::microseconds(80));
}

void simulate_geometry_stage(const char* case_id) {
    cae::TaskScope geometry_scope("Geometry", "Geometry", cae::Level::Info, "workflow");
    CAE_LOG(Info).module("Geometry")
        .message("Geometry workflow started for case {}.", case_id)
        .submit();

    for (int part = 1; part <= 12; ++part) {
        CAE_LOG(Info).module("Geometry")
            .message("Imported CAD body {:02d}/12 from STEP assembly.", part)
            .submit();
        CAE_LOG(Debug).module("Geometry")
            .message("Computed bounding box for body {:02d}: diagonal={:.2f} mm.", part, 120.0 + part * 3.5)
            .submit();
        CAE_LOG(Info).module("Geometry")
            .message("Detected feature set for body {:02d}: faces={}, edges={}.", part, 80 + part * 4, 220 + part * 9)
            .submit();
        if (part % 4 == 0) {
            CAE_LOG(Warn).module("Geometry")
                .message("Small sliver faces found on body {:02d}; queued for repair.", part)
                .submit();
        } else {
            CAE_LOG(Info).module("Geometry")
                .message("Topology check passed for body {:02d}.", part)
                .submit();
        }
        pause_between_events();
    }

    for (int repair = 1; repair <= 8; ++repair) {
        CAE_LOG(Info).module("Geometry")
            .message("Healing operation {:02d}/08 merged tolerant edges and closed gaps.", repair)
            .submit();
        pause_between_events();
    }

    CAE_LOG(Info).module("Geometry")
        .message("Named selections created: inlet, outlet, wall, symmetry, bolt_holes.")
        .submit();
    CAE_LOG(Info)
        .module("Geometry")
        .stage("Geometry")
        .action("validation_summary")
        .event_type(cae::EventType::Geometry)
        .phase(cae::EventPhase::Progress)
        .domain(cae::Domain::Pre)
        .entity("geometry", "validation")
        .metric("watertight_solids", static_cast<std::int64_t>(12))
        .metric("repaired_edges", static_cast<std::int64_t>(31))
        .metric("suppressed_faces", static_cast<std::int64_t>(9))
        .message("Geometry validation summary completed.")
        .submit();
    CAE_LOG(Info).module("Geometry")
        .message("Geometry workflow completed for case {}.", case_id)
        .submit();
}

void simulate_mesh_stage(const char* case_id) {
    cae::TaskScope mesh_scope("Mesh", "Mesh", cae::Level::Info, "workflow");
    CAE_LOG(Info).module("Mesh")
        .message("Mesh workflow started for case {}.", case_id)
        .submit();

    for (int region = 1; region <= 10; ++region) {
        CAE_LOG(Info).module("Mesh")
            .message("Assigned sizing control to region {:02d}: target={:.2f} mm.", region, 3.0 + region * 0.15)
            .submit();
        CAE_LOG(Debug).module("Mesh")
            .message("Inflation layer setup for region {:02d}: layers={}, growth={:.2f}.", region, 5 + region % 4, 1.18)
            .submit();
        CAE_LOG(Info).module("Mesh")
            .message("Generated surface mesh for region {:02d}: triangles={}.", region, 4200 + region * 370)
            .submit();
        CAE_LOG(Info).module("Mesh")
            .message("Generated volume mesh for region {:02d}: cells={}.", region, 18000 + region * 1250)
            .submit();
        if (region % 3 == 0) {
            CAE_LOG(Warn).module("Mesh")
                .message("High skewness pocket detected in region {:02d}; local remesh requested.", region)
                .submit();
        } else {
            CAE_LOG(Info).module("Mesh")
                .message("Quality gate passed for region {:02d}: max_skewness={:.2f}.", region, 0.72 + region * 0.01)
                .submit();
        }
        pause_between_events();
    }

    for (int pass = 1; pass <= 20; ++pass) {
        CAE_LOG(Info).module("Mesh")
            .message("Adaptive refinement pass {:02d}/20 updated curvature and proximity cells.", pass)
            .submit();
        if (pass % 5 == 0) {
            CAE_LOG(Warn).module("Mesh")
                .message("Refinement pass {:02d} increased cell count above planning target.", pass)
                .submit();
        }
        pause_between_events();
    }

    for (int check = 1; check <= 10; ++check) {
        CAE_LOG(Debug).module("Mesh")
            .message("Mesh metric sample {:02d}: orthogonal_quality={:.3f}.", check, 0.91 - check * 0.004)
            .submit();
        pause_between_events();
    }

    for (int interface_id = 1; interface_id <= 16; ++interface_id) {
        CAE_LOG(Info).module("Mesh")
            .message("Created conformal interface {:02d}/16 between adjacent mesh zones.", interface_id)
            .submit();
        CAE_LOG(Debug).module("Mesh")
            .message("Interface {:02d}/16 node matching completed with tolerance {:.4f} mm.", interface_id, 0.0025)
            .submit();
        pause_between_events();
    }

    CAE_LOG(Info)
        .module("Mesh")
        .stage("Mesh")
        .action("export_summary")
        .event_type(cae::EventType::Mesh)
        .phase(cae::EventPhase::Progress)
        .domain(cae::Domain::Pre)
        .entity("mesh", "volume_mesh")
        .metric("nodes", static_cast<std::int64_t>(284120))
        .metric("cells", static_cast<std::int64_t>(1513840))
        .metric("elements", static_cast<std::int64_t>(1513840))
        .metric("partitions", static_cast<std::int64_t>(8))
        .message("Mesh export summary completed.")
        .submit();
    CAE_LOG(Info).module("Mesh")
        .message("Mesh workflow completed for case {}.", case_id)
        .submit();
}

void simulate_solver_stage(const char* case_id) {
    cae::TaskScope solver_scope("Solver", "Solver", cae::Level::Info, "workflow");
    CAE_LOG(Info).module("Solver")
        .message("Solver workflow started for case {}.", case_id)
        .submit();

    for (int setup = 1; setup <= 18; ++setup) {
        CAE_LOG(Info).module("Solver")
            .message("Solver setup step {:02d}/18 applied material, load, and boundary data.", setup)
            .submit();
        pause_between_events();
    }

    {
        cae::TaskScope iteration_scope("Solver", "Iteration", cae::Level::Info, "nonlinear_loop");
        for (int iteration = 1; iteration <= 240; ++iteration) {
            const double residual = 1.0 / (iteration + 8.0);
            const double courant = 0.35 + (iteration % 12) * 0.03;
            CAE_LOG(Info)
                .module("Solver")
                .stage("Iteration")
                .action("nonlinear_step")
                .event_type(cae::EventType::Solve)
                .phase(cae::EventPhase::Progress)
                .domain(cae::Domain::CFD)
                .entity("solver", "nonlinear_loop")
                .metric("iteration", static_cast<std::int64_t>(iteration))
                .metric("residual", residual)
                .metric("courant", courant)
                .message("Nonlinear iteration {:03d}/240 completed.", iteration)
                .submit();
            if (iteration % 40 == 0) {
                CAE_LOG(Warn).module("Solver")
                    .message("Residual plateau near iteration {:03d}; under-relaxation adjusted.", iteration)
                    .submit();
            }
            pause_between_events();
        }
    }

    for (int partition = 1; partition <= 18; ++partition) {
        CAE_LOG(Debug).module("Solver")
            .message("Partition {:02d}/18 exchanged interface flux and halo cells.", partition)
            .submit();
        pause_between_events();
    }

    for (int checkpoint = 1; checkpoint <= 18; ++checkpoint) {
        CAE_LOG(Info).module("Solver")
            .message("Checkpoint {:02d}/18 written: displacement, stress, and convergence fields.", checkpoint)
            .submit();
        pause_between_events();
    }
}

void simulate_postprocess_stage(const char* case_id) {
    cae::TaskScope postprocess_scope("PostProcess", "PostProcess", cae::Level::Info, "workflow");
    CAE_LOG(Info).module("PostProcess")
        .message("Post-processing workflow started for case {}.", case_id)
        .submit();

    for (int field = 1; field <= 12; ++field) {
        CAE_LOG(Info).module("PostProcess")
            .message("Loaded result field {:02d}/12: scalar/vector dataset ready.", field)
            .submit();
        CAE_LOG(Debug).module("PostProcess")
            .message("Computed min/max envelope for result field {:02d}.", field)
            .submit();
        if (field % 6 == 0) {
            CAE_LOG(Warn).module("PostProcess")
                .message("Result field {:02d} contains localized hot spot above review threshold.", field)
                .submit();
        }
        pause_between_events();
    }

    for (int plot = 1; plot <= 18; ++plot) {
        CAE_LOG(Info).module("PostProcess")
            .message("Generated contour plot {:02d}/18 for stress, strain, velocity, or pressure.", plot)
            .submit();
        pause_between_events();
    }

    for (int probe = 1; probe <= 12; ++probe) {
        CAE_LOG(Info).module("PostProcess")
            .message("Extracted probe curve {:02d}/12 along named path.", probe)
            .submit();
        pause_between_events();
    }

    for (int export_id = 1; export_id <= 4; ++export_id) {
        CAE_LOG(Info).module("PostProcess")
            .message("Exported deliverable {:02d}/04: report table, image, VTK, or CSV.", export_id)
            .submit();
        pause_between_events();
    }

    for (int review = 1; review <= 7; ++review) {
        CAE_LOG(Info).module("PostProcess")
            .message("Design review metric {:02d}/07 added to final CAE evidence package.", review)
            .submit();
        pause_between_events();
    }

    CAE_LOG(Info)
        .module("PostProcess")
        .stage("PostProcess")
        .action("engineering_summary")
        .event_type(cae::EventType::PostProcess)
        .phase(cae::EventPhase::Progress)
        .domain(cae::Domain::Post)
        .entity("postprocess", "engineering_summary")
        .metric("max_stress", 248.6)
        .metric("safety_factor", 1.72)
        .message("Engineering summary completed.")
        .submit();
    CAE_LOG(Info).module("PostProcess")
        .message("Post-processing workflow completed for case {}.", case_id)
        .submit();
}

int main(int argc, char* argv[]) {
    const char* proc_id = (argc > 1) ? argv[1] : "Single";
    const std::string case_id = std::string("CAE_") + proc_id;

    cae::init("cae_logger_config.ini");
    cae::set_session(proc_id);
    cae::set_job_id(case_id);
    cae::set_node_id("local-workstation");
    if (std::string(proc_id).rfind("Proc_", 0) == 0) {
        cae::set_mpi_rank(std::stoi(std::string(proc_id).substr(5)) - 1);
    }
    {
        cae::TaskScope workflow_scope("System", "Workflow", cae::Level::Info, "full_pipeline");

        CAE_LOG(Info).module("System")
            .message("CAE application instance [{}] started.", proc_id)
            .submit();

        simulate_geometry_stage(case_id.c_str());
        simulate_mesh_stage(case_id.c_str());
        simulate_solver_stage(case_id.c_str());
        simulate_postprocess_stage(case_id.c_str());

        CAE_LOG(Info).module("System")
            .message("CAE application instance [{}] completed full geometry-mesh-solve-post workflow.", proc_id)
            .submit();
    }
    cae::shutdown();

    return 0;
}
