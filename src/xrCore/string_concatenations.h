#ifndef STRING_CONCATENATIONS_H
#define STRING_CONCATENATIONS_H


LPSTR XRCORE_API strconcat(int dest_sz, char* dest, const char* S1, const char* S2);
LPSTR XRCORE_API strconcat(int dest_sz, char* dest, const char* S1, const char* S2, const char* S3);
LPSTR XRCORE_API strconcat(int dest_sz, char* dest, const char* S1, const char* S2, const char* S3, const char* S4);
LPSTR XRCORE_API strconcat(int dest_sz, char* dest, const char* S1, const char* S2, const char* S3, const char* S4,
                           const char* S5);
LPSTR XRCORE_API strconcat(int dest_sz, char* dest, const char* S1, const char* S2, const char* S3, const char* S4,
                           const char* S5, const char* S6);


// warning: do not comment this macro, as stack overflow check is very light
// (consumes ~1% performance of STRCONCAT macro)
#define STRCONCAT_STACKOVERFLOW_CHECK

#ifdef STRCONCAT_STACKOVERFLOW_CHECK

#define STRCONCAT(dest, ...) \
 do { \
 xray::core::detail::string_tupples STRCONCAT_tupples_unique_identifier(__VA_ARGS__); \
 u32 STRCONCAT_buffer_size = STRCONCAT_tupples_unique_identifier.size(); \
 xray::core::detail::check_stack_overflow(STRCONCAT_buffer_size); \
 (dest) = (LPSTR)_alloca(STRCONCAT_buffer_size); \
 STRCONCAT_tupples_unique_identifier.concat (dest); \
  } while (0)

#else //#ifdef STRCONCAT_STACKOVERFLOW_CHECK

#define STRCONCAT(dest, ...) \
 do { \
 xray::core::detail::string_tupples STRCONCAT_tupples_unique_identifier(__VA_ARGS__); \
 (dest) = (LPSTR)_alloca(STRCONCAT_tupples_unique_identifier.size()); \
 STRCONCAT_tupples_unique_identifier.concat (dest); \
  } while (0)

#endif //#ifdef STRCONCAT_STACKOVERFLOW_CHECK

#include "string_concatenations_inline.h"

// Giperion XRay Oxygen - ultimate version of strconcat
template<typename StringReceiverType, typename... ArgList>
char* xr_strconcat(StringReceiverType& receiver, ArgList... args)
{
	static_assert(std::is_array< StringReceiverType>::value); // must be array...
	static_assert(std::is_same<typename std::remove_extent< StringReceiverType>::type, char>::value); // ... of chars

	char* pStrCursor = &receiver[0];
	char* pStrEnd = &receiver[0] + sizeof(StringReceiverType);
	int dummy[] = { _strconcatSingle(pStrCursor, pStrEnd, args)... };
	(void)dummy;

	*pStrCursor = '\0';
	return &receiver[0];
}

int XRCORE_API _strconcatSingle(char*& destPtr, char* pDestEnd, const char* Str);


#endif // #ifndef STRING_CONCATENATIONS_H