#pragma once

#include <cerrno>
#include <cstddef>
#include <cstdint>
#include <string>
#include <system_error>
#include <vector>

#ifdef _WIN32
    #include <direct.h>
    #include <io.h>
    #include <sys/stat.h>
#else
    #include <dirent.h>
    #include <sys/stat.h>
    #include <sys/types.h>
    #include <unistd.h>
#endif

namespace cae
{
namespace detail
{
namespace fs
{

    class path
    {
      public:

        path()
        {
        }

        path(const char* thePath) : myPath(thePath != nullptr ? thePath : "")
        {
        }

        path(const std::string& thePath) : myPath(thePath)
        {
        }

        const std::string& string() const
        {
            return myPath;
        }

        const char* c_str() const
        {
            return myPath.c_str();
        }

        bool empty() const
        {
            return myPath.empty();
        }

        path parent_path() const
        {
            const std::size_t aPos = myPath.find_last_of("/\\");
            if (aPos == std::string::npos)
            {
                return path();
            }
            if (aPos == 0)
            {
                return path(myPath.substr(0, 1));
            }
            return path(myPath.substr(0, aPos));
        }

        path stem() const
        {
            const std::string aFileName = filename_string();
            const std::size_t aDot = aFileName.find_last_of('.');
            if (aDot == std::string::npos || aDot == 0)
            {
                return path(aFileName);
            }
            return path(aFileName.substr(0, aDot));
        }

        path extension() const
        {
            const std::string aFileName = filename_string();
            const std::size_t aDot = aFileName.find_last_of('.');
            if (aDot == std::string::npos || aDot == 0)
            {
                return path();
            }
            return path(aFileName.substr(aDot));
        }

        friend bool operator==(const path& theLeft, const path& theRight)
        {
            return theLeft.myPath == theRight.myPath;
        }

        friend bool operator!=(const path& theLeft, const path& theRight)
        {
            return !(theLeft == theRight);
        }

        friend path operator/(const path& theLeft, const path& theRight)
        {
            if (theLeft.myPath.empty())
            {
                return theRight;
            }
            if (theRight.myPath.empty())
            {
                return theLeft;
            }
            if (is_absolute(theRight.myPath))
            {
                return theRight;
            }

            const char aLast = theLeft.myPath[theLeft.myPath.size() - 1];
            if (aLast == '/' || aLast == '\\')
            {
                return path(theLeft.myPath + theRight.myPath);
            }
            return path(theLeft.myPath + "/" + theRight.myPath);
        }

        friend path operator/(const path& theLeft, const char* theRight)
        {
            return theLeft / path(theRight);
        }

        friend path operator/(const path& theLeft, const std::string& theRight)
        {
            return theLeft / path(theRight);
        }

      private:

        static bool is_absolute(const std::string& thePath)
        {
            if (thePath.empty())
            {
                return false;
            }
            if (thePath[0] == '/' || thePath[0] == '\\')
            {
                return true;
            }
            return thePath.size() > 2 && thePath[1] == ':';
        }

        std::string filename_string() const
        {
            const std::size_t aPos = myPath.find_last_of("/\\");
            if (aPos == std::string::npos)
            {
                return myPath;
            }
            return myPath.substr(aPos + 1);
        }

      private:

        std::string myPath;
    };

#ifdef _WIN32
    typedef struct _stat file_status;
#else
    typedef struct stat file_status;
#endif

    struct FileTime
    {
        std::int64_t seconds;
        std::int64_t nanoseconds;

        FileTime() : seconds(0), nanoseconds(0)
        {
        }

        FileTime(std::int64_t theSeconds, std::int64_t theNanoseconds)
        : seconds(theSeconds), nanoseconds(theNanoseconds)
        {
        }
    };

    inline bool operator==(const FileTime& theLeft, const FileTime& theRight)
    {
        return theLeft.seconds == theRight.seconds && theLeft.nanoseconds == theRight.nanoseconds;
    }

    inline bool operator!=(const FileTime& theLeft, const FileTime& theRight)
    {
        return !(theLeft == theRight);
    }

    inline void clear_error(std::error_code& theError)
    {
        theError.clear();
    }

    inline void set_errno_error(std::error_code& theError)
    {
        theError = std::error_code(errno, std::generic_category());
    }

    inline bool stat_path(const path& thePath, file_status& theStatus)
    {
#ifdef _WIN32
        return ::_stat(thePath.c_str(), &theStatus) == 0;
#else
        return ::stat(thePath.c_str(), &theStatus) == 0;
#endif
    }

    inline bool exists(const path& thePath, std::error_code& theError)
    {
        file_status aStatus;
        if (stat_path(thePath, aStatus))
        {
            clear_error(theError);
            return true;
        }

        if (errno == ENOENT || errno == ENOTDIR)
        {
            clear_error(theError);
        }
        else
        {
            set_errno_error(theError);
        }
        return false;
    }

    inline bool exists(const path& thePath)
    {
        std::error_code anError;
        return exists(thePath, anError);
    }

    inline bool is_directory(const path& thePath)
    {
        file_status aStatus;
        return stat_path(thePath, aStatus) && (aStatus.st_mode & S_IFDIR) != 0;
    }

    inline bool is_regular_file(const path& thePath)
    {
        file_status aStatus;
        return stat_path(thePath, aStatus) && (aStatus.st_mode & S_IFREG) != 0;
    }

    inline bool create_directory(const path& thePath)
    {
#ifdef _WIN32
        return ::_mkdir(thePath.c_str()) == 0 || errno == EEXIST;
#else
        return ::mkdir(thePath.c_str(), 0777) == 0 || errno == EEXIST;
#endif
    }

    inline bool create_directories(const path& thePath)
    {
        const std::string aPath = thePath.string();
        if (aPath.empty() || is_directory(thePath))
        {
            return false;
        }

        std::string aCurrent;
        std::size_t anIndex = 0;
        if (aPath[0] == '/' || aPath[0] == '\\')
        {
            aCurrent = aPath.substr(0, 1);
            anIndex = 1;
        }
        else if (aPath.size() > 2 && aPath[1] == ':')
        {
            aCurrent = aPath.substr(0, 2);
            anIndex = 2;
        }

        bool hasCreated = false;
        for (; anIndex < aPath.size(); ++anIndex)
        {
            const char aChar = aPath[anIndex];
            if (aChar == '/' || aChar == '\\')
            {
                if (!aCurrent.empty() && !is_directory(path(aCurrent)))
                {
                    hasCreated = create_directory(path(aCurrent)) || hasCreated;
                }
            }
            aCurrent += aChar;
        }

        if (!aCurrent.empty() && !is_directory(path(aCurrent)))
        {
            hasCreated = create_directory(path(aCurrent)) || hasCreated;
        }
        return hasCreated;
    }

    inline bool create_directories(const std::string& thePath)
    {
        return create_directories(path(thePath));
    }

    inline std::uint64_t file_size(const path& thePath, std::error_code& theError)
    {
        file_status aStatus;
        if (!stat_path(thePath, aStatus))
        {
            set_errno_error(theError);
            return 0;
        }

        clear_error(theError);
        return static_cast<std::uint64_t>(aStatus.st_size);
    }

    inline bool remove(const path& thePath, std::error_code& theError)
    {
#ifdef _WIN32
        const int aResult = ::_unlink(thePath.c_str());
#else
        const int aResult = ::unlink(thePath.c_str());
#endif
        if (aResult == 0)
        {
            clear_error(theError);
            return true;
        }
        if (errno == ENOENT)
        {
            clear_error(theError);
            return false;
        }

        set_errno_error(theError);
        return false;
    }

    inline FileTime last_write_time(const path& thePath, std::error_code& theError)
    {
        file_status aStatus;
        if (!stat_path(thePath, aStatus))
        {
            set_errno_error(theError);
            return FileTime();
        }

        clear_error(theError);
#ifdef _WIN32
        return FileTime(static_cast<std::int64_t>(aStatus.st_mtime), 0);
#elif defined(__APPLE__)
        return FileTime(static_cast<std::int64_t>(aStatus.st_mtimespec.tv_sec),
                        static_cast<std::int64_t>(aStatus.st_mtimespec.tv_nsec));
#else
        return FileTime(static_cast<std::int64_t>(aStatus.st_mtim.tv_sec),
                        static_cast<std::int64_t>(aStatus.st_mtim.tv_nsec));
#endif
    }

    inline std::vector<path> regular_files(const path& theDirectory, std::error_code& theError)
    {
        std::vector<path> aFiles;
#ifdef _WIN32
        const path aPattern = theDirectory / "*";
        struct _finddata_t aFindData;
        const intptr_t aHandle = ::_findfirst(aPattern.c_str(), &aFindData);
        if (aHandle == -1)
        {
            if (errno == ENOENT)
            {
                clear_error(theError);
            }
            else
            {
                set_errno_error(theError);
            }
            return aFiles;
        }

        do
        {
            const std::string aName(aFindData.name);
            if (aName == "." || aName == "..")
            {
                continue;
            }
            const path aCandidate = theDirectory / aName;
            if (is_regular_file(aCandidate))
            {
                aFiles.push_back(aCandidate);
            }
        } while (::_findnext(aHandle, &aFindData) == 0);
        ::_findclose(aHandle);
        clear_error(theError);
#else
        DIR* aDir = ::opendir(theDirectory.c_str());
        if (aDir == nullptr)
        {
            if (errno == ENOENT)
            {
                clear_error(theError);
            }
            else
            {
                set_errno_error(theError);
            }
            return aFiles;
        }

        errno = 0;
        while (dirent* anEntry = ::readdir(aDir))
        {
            const std::string aName(anEntry->d_name);
            if (aName == "." || aName == "..")
            {
                continue;
            }
            const path aCandidate = theDirectory / aName;
            if (is_regular_file(aCandidate))
            {
                aFiles.push_back(aCandidate);
            }
        }
        if (errno != 0)
        {
            set_errno_error(theError);
        }
        else
        {
            clear_error(theError);
        }
        ::closedir(aDir);
#endif
        return aFiles;
    }

} // namespace fs
} // namespace detail
} // namespace cae
