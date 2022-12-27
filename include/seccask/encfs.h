#pragma once

#include <string>

extern "C" {
extern unsigned char *g_component_key; /*< 256-bit key */
}

namespace seccask {
namespace encfs {
void InitWithKey(const std::string &component_key);
}  // namespace encfs
}  // namespace seccask