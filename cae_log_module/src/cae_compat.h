#pragma once

#include <cstddef>
#include <cstdint>
#include <cstring>
#include <new>
#include <stdexcept>
#include <string>
#include <type_traits>
#include <utility>

namespace cae
{

namespace detail
{
    constexpr std::size_t c_string_length(const char* theValue)
    {
        return theValue == nullptr || *theValue == '\0' ? 0 : 1 + c_string_length(theValue + 1);
    }
} // namespace detail

struct nullopt_t
{
    explicit constexpr nullopt_t(int)
    {
    }
};

static const nullopt_t nullopt(0);

template<typename T>
class optional
{
  public:

    optional() : myHasValue(false)
    {
    }

    optional(nullopt_t) : myHasValue(false)
    {
    }

    optional(const T& theValue) : myHasValue(false)
    {
        construct(theValue);
    }

    optional(T&& theValue) : myHasValue(false)
    {
        construct(std::move(theValue));
    }

    optional(const optional& theOther) : myHasValue(false)
    {
        if (theOther.has_value())
        {
            construct(*theOther);
        }
    }

    optional(optional&& theOther) : myHasValue(false)
    {
        if (theOther.has_value())
        {
            construct(std::move(*theOther));
        }
    }

    ~optional()
    {
        reset();
    }

    optional& operator=(nullopt_t)
    {
        reset();
        return *this;
    }

    optional& operator=(const optional& theOther)
    {
        if (this == &theOther)
        {
            return *this;
        }

        if (theOther.has_value())
        {
            assign(*theOther);
        }
        else
        {
            reset();
        }
        return *this;
    }

    optional& operator=(optional&& theOther)
    {
        if (this == &theOther)
        {
            return *this;
        }

        if (theOther.has_value())
        {
            assign(std::move(*theOther));
        }
        else
        {
            reset();
        }
        return *this;
    }

    optional& operator=(const T& theValue)
    {
        assign(theValue);
        return *this;
    }

    optional& operator=(T&& theValue)
    {
        assign(std::move(theValue));
        return *this;
    }

    bool has_value() const
    {
        return myHasValue;
    }

    explicit operator bool() const
    {
        return myHasValue;
    }

    T& operator*()
    {
        return *ptr();
    }

    const T& operator*() const
    {
        return *ptr();
    }

    T* operator->()
    {
        return ptr();
    }

    const T* operator->() const
    {
        return ptr();
    }

    T& value()
    {
        if (!myHasValue)
        {
            throw std::logic_error("bad optional access");
        }
        return *ptr();
    }

    const T& value() const
    {
        if (!myHasValue)
        {
            throw std::logic_error("bad optional access");
        }
        return *ptr();
    }

    void reset()
    {
        if (myHasValue)
        {
            ptr()->~T();
            myHasValue = false;
        }
    }

  private:

    template<typename Value>
    void construct(Value&& theValue)
    {
        new (&myStorage) T(std::forward<Value>(theValue));
        myHasValue = true;
    }

    template<typename Value>
    void assign(Value&& theValue)
    {
        if (myHasValue)
        {
            *ptr() = std::forward<Value>(theValue);
        }
        else
        {
            construct(std::forward<Value>(theValue));
        }
    }

    T* ptr()
    {
        return reinterpret_cast<T*>(&myStorage);
    }

    const T* ptr() const
    {
        return reinterpret_cast<const T*>(&myStorage);
    }

  private:

    typename std::aligned_storage<sizeof(T), std::alignment_of<T>::value>::type myStorage;
    bool myHasValue;
};

class StringView
{
  public:

    constexpr StringView() : myData(""), mySize(0)
    {
    }

    constexpr StringView(const char* theData) : myData(theData == nullptr ? "" : theData),
                                                mySize(detail::c_string_length(theData))
    {
    }

    StringView(const std::string& theValue) : myData(theValue.data()), mySize(theValue.size())
    {
    }

    const char* data() const
    {
        return myData;
    }

    std::size_t size() const
    {
        return mySize;
    }

    bool empty() const
    {
        return mySize == 0;
    }

    std::string to_string() const
    {
        return std::string(myData, mySize);
    }

  private:

    const char* myData;
    std::size_t mySize;
};

} // namespace cae
