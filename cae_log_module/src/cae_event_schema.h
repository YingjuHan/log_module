#pragma once

#include <array>

#include "cae_compat.h"

namespace cae
{

//! Current structured event schema version written to JSONL records.
static const char* const kCaeEventSchemaVersion = "cae_event_v1";

//! Prefix used when flattening metric keys into tabular exports.
static const char* const kCaeEventMetricColumnPrefix = "metric_";

//! String fields that every structured CAE event row must provide.
static const std::array<StringView, 23> kCaeEventRequiredStringFields = {
    "timestamp", "date",        "time",           "source",     "component",         "stage",
    "action",    "level",       "message",        "event_kind", "trace_id",          "span_id",
    "session",   "thread_name", "schema_version", "event_id",   "event_type",        "phase",
    "domain",    "entity_type", "entity_name",    "job_id",     "global_sequence_id"};

//! Integer fields that every structured CAE event row must provide.
static const std::array<StringView, 6> kCaeEventRequiredIntegerFields =
    {"duration_us", "size", "sequence", "logical_time", "timestamp_epoch_us", "monotonic_us"};

//! String fields that may be null when the event has no related value.
static const std::array<StringView, 6> kCaeEventNullableStringFields =
    {"parent_span_id", "parent_event_id", "object_type", "object_name", "result", "reason"};

//! Entity key used by reports to aggregate events around a domain object.
struct CAEEventEntity
{
    //! Entity category, such as `case`, `mesh`, `file`, or `solver`.
    StringView type;
    //! Stable entity identifier after caller-side redaction.
    StringView name;
};

//! High-level event category used by schema-aware reporting tools.
enum class EventType
{
    //! Geometry import, healing, topology, or CAD preparation event.
    Geometry,
    //! Mesh generation, quality, partitioning, or mesh I/O event.
    Mesh,
    //! Solver setup, iteration, convergence, or residual event.
    Solve,
    //! Generic file, database, import, or export event.
    IO,
    //! User-interface interaction or presentation event.
    UI,
    //! MPI, rank, communication, or distributed execution event.
    MPI,
    //! Post-processing, visualization, query, or report event.
    PostProcess,
    //! Logger, runtime, environment, or workflow infrastructure event.
    System,
    //! Category could not be inferred or was intentionally left generic.
    Unknown
};

//! Lifecycle phase for schema-aware event aggregation.
enum class EventPhase
{
    //! Beginning of a lifecycle or action.
    Start,
    //! Intermediate progress within a lifecycle or action.
    Progress,
    //! End of a lifecycle or action.
    End,
    //! Phase could not be inferred or was intentionally left generic.
    Unknown
};

//! Engineering or product domain associated with an event.
enum class Domain
{
    //! Computational fluid dynamics domain.
    CFD,
    //! Finite-element or structural simulation domain.
    FEM,
    //! Pre-processing domain.
    Pre,
    //! Post-processing domain.
    Post,
    //! Infrastructure, runtime, or cross-domain system behavior.
    System,
    //! Domain could not be inferred or was intentionally left generic.
    Unknown
};

//! Async queue behavior when producers outpace the backend.
enum class AsyncOverflowPolicy
{
    //! Block producers until queue capacity becomes available.
    Block,
    //! Drop the oldest queued record to accept the newest record.
    OverrunOldest
};

//! Converts an event type enum to its schema string value.
inline StringView to_schema_value(EventType event_type)
{
    switch (event_type)
    {
        case EventType::Geometry: return "geometry";
        case EventType::Mesh: return "mesh";
        case EventType::Solve: return "solve";
        case EventType::IO: return "io";
        case EventType::UI: return "ui";
        case EventType::MPI: return "mpi";
        case EventType::PostProcess: return "postprocess";
        case EventType::System: return "system";
        case EventType::Unknown:
        default: return "unknown";
    }
}

//! Converts an event phase enum to its schema string value.
inline StringView to_schema_value(EventPhase phase)
{
    switch (phase)
    {
        case EventPhase::Start: return "start";
        case EventPhase::Progress: return "progress";
        case EventPhase::End: return "end";
        case EventPhase::Unknown:
        default: return "unknown";
    }
}

//! Converts a domain enum to its schema string value.
inline StringView to_schema_value(Domain domain)
{
    switch (domain)
    {
        case Domain::CFD: return "cfd";
        case Domain::FEM: return "fem";
        case Domain::Pre: return "pre";
        case Domain::Post: return "post";
        case Domain::System: return "system";
        case Domain::Unknown:
        default: return "unknown";
    }
}

} // namespace cae
