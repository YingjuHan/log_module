#include "cae_log_builder.h"

#include "cae_logger_core.h"
#include "cae_logger_detail.h"

namespace cae
{

//=======================================================================
// function : LogBuilder::LogBuilder
// purpose  :
//=======================================================================
LogBuilder::LogBuilder(Level theLevel) : myLevel(theLevel)
{
}

//=======================================================================
// function : LogBuilder::module
// purpose  :
//=======================================================================
LogBuilder& LogBuilder::module(const char* theModule)
{
    myModule = theModule != nullptr ? theModule : "";
    return *this;
}

//=======================================================================
// function : LogBuilder::stage
// purpose  :
//=======================================================================
LogBuilder& LogBuilder::stage(const char* theStage)
{
    myStage = theStage != nullptr ? theStage : "";
    return *this;
}

//=======================================================================
// function : LogBuilder::action
// purpose  :
//=======================================================================
LogBuilder& LogBuilder::action(const char* theAction)
{
    myAction = theAction != nullptr ? theAction : "";
    return *this;
}

//=======================================================================
// function : LogBuilder::object
// purpose  :
//=======================================================================
LogBuilder& LogBuilder::object(const char* theObjectType, const char* theObjectName)
{
    myObjectType = theObjectType != nullptr ? theObjectType : "";
    myObjectName = theObjectName != nullptr ? theObjectName : "";
    return *this;
}

//=======================================================================
// function : LogBuilder::entity
// purpose  :
//=======================================================================
LogBuilder& LogBuilder::entity(const char* theEntityType, const char* theEntityName)
{
    myEntityType = theEntityType != nullptr ? theEntityType : "";
    myEntityName = theEntityName != nullptr ? theEntityName : "";
    return *this;
}

//=======================================================================
// function : LogBuilder::event_type
// purpose  :
//=======================================================================
LogBuilder& LogBuilder::event_type(EventType theEventType)
{
    myEventType = theEventType;
    return *this;
}

//=======================================================================
// function : LogBuilder::phase
// purpose  :
//=======================================================================
LogBuilder& LogBuilder::phase(EventPhase thePhase)
{
    myPhase = thePhase;
    return *this;
}

//=======================================================================
// function : LogBuilder::domain
// purpose  :
//=======================================================================
LogBuilder& LogBuilder::domain(Domain theDomain)
{
    myDomain = theDomain;
    return *this;
}

//=======================================================================
// function : LogBuilder::result
// purpose  :
//=======================================================================
LogBuilder& LogBuilder::result(const char* theResult)
{
    myResult = theResult != nullptr ? theResult : "";
    return *this;
}

//=======================================================================
// function : LogBuilder::reason
// purpose  :
//=======================================================================
LogBuilder& LogBuilder::reason(const char* theReason)
{
    myReason = theReason != nullptr ? theReason : "";
    return *this;
}

//=======================================================================
// function : LogBuilder::metric
// purpose  :
//=======================================================================
LogBuilder& LogBuilder::metric(const char* theKey, std::int64_t theValue)
{
    if (theKey != nullptr && *theKey != '\0')
    {
        myMetrics[theKey] = theValue;
    }
    return *this;
}

//=======================================================================
// function : LogBuilder::metric
// purpose  :
//=======================================================================
LogBuilder& LogBuilder::metric(const char* theKey, double theValue)
{
    if (theKey != nullptr && *theKey != '\0')
    {
        myMetrics[theKey] = theValue;
    }
    return *this;
}

//=======================================================================
// function : LogBuilder::metric
// purpose  :
//=======================================================================
LogBuilder& LogBuilder::metric(const char* theKey, bool theValue)
{
    if (theKey != nullptr && *theKey != '\0')
    {
        myMetrics[theKey] = theValue;
    }
    return *this;
}

//=======================================================================
// function : LogBuilder::metric
// purpose  :
//=======================================================================
LogBuilder& LogBuilder::metric(const char* theKey, const std::string& theValue)
{
    if (theKey != nullptr && *theKey != '\0')
    {
        myMetrics[theKey] = theValue;
    }
    return *this;
}

//=======================================================================
// function : LogBuilder::metric
// purpose  :
//=======================================================================
LogBuilder& LogBuilder::metric(const char* theKey, const char* theValue)
{
    if (theKey != nullptr && *theKey != '\0')
    {
        myMetrics[theKey] = theValue != nullptr ? std::string(theValue) : std::string();
    }
    return *this;
}

//=======================================================================
// function : LogBuilder::duration_us
// purpose  :
//=======================================================================
LogBuilder& LogBuilder::duration_us(std::uint64_t theDurationUs)
{
    myDurationUs = theDurationUs;
    myHasDuration = true;
    return *this;
}

//=======================================================================
// function : LogBuilder::submit
// purpose  :
//=======================================================================
void LogBuilder::submit() const
{
    detail::LoggerCore::instance().emit_structured(
        myModule,
        myStage,
        myAction,
        myObjectType,
        myObjectName,
        myResult,
        myReason,
        myMetrics,
        myEventType == EventType::Unknown ? std::string() : detail::event_type_to_string(myEventType),
        myPhase == EventPhase::Unknown ? std::string() : detail::event_phase_to_string(myPhase),
        myDomain == Domain::Unknown ? std::string() : detail::domain_to_string(myDomain),
        myEntityType,
        myEntityName,
        myLevel,
        myMessage,
        myHasDuration ? detail::EventKind::Span : detail::EventKind::Point,
        myDurationUs);
}

} // namespace cae
