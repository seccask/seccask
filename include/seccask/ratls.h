#pragma once

#include <INIReader.h>

#include <boost/algorithm/hex.hpp>
#include <boost/asio/ssl.hpp>
#include <boost/filesystem.hpp>

#include "seccask/util.h"

namespace seccask {
/* expected SGX measurements in binary form. Ignore ISV */
static char g_expected_mrenclave[32];
static char g_expected_mrsigner[32];

/**
 * @brief RA-TLS - our own callback to verify SGX measurements
 *
 * Currently ignore ISV product ID and ISV SVN
 *
 * @param mrenclave Enclave Measurement
 * @param mrsigner Signer Measurement
 * @param isv_prod_id ISV product ID
 * @param isv_svn ISV SVN
 * @return int
 */
static int custom_tls_verification_callback(const char* mrenclave,
                                            const char* mrsigner,
                                            const char* isv_prod_id,
                                            const char* isv_svn);

class RATLS {
 public:
  inline static constexpr const char* kClassName = "RA-TLS";

  inline static RATLS& Get() {
    static RATLS instance;
    return instance;
  }

  inline static void SetupSSLContext(boost::asio::ssl::context& ctx) {
    Get().DoSetupSSLContext(ctx);
  }

  inline void InitQuoteGeneration() { DoInitQuoteGeneration(); }

  inline void InitVerification() { DoInitVerification(); }

  /**
   * @brief Without doing actual SGX quote verification, just simply print the
   * certificate's subject name.
   *
   * @return always true
   */
  bool PrintCertOnly(bool preverified, boost::asio::ssl::verify_context& ctx);

  /**
   * @brief Perform SGX quote verification
   *
   * @return true if verification passed
   * @return false if verification failed
   */
  bool Verify(bool preverified, boost::asio::ssl::verify_context& ctx);

 private:
  RATLS()
      : x509_cert_(nullptr),
        der_key_(nullptr),
        der_key_size_(0),
        ra_tls_verify_lib_(nullptr),
        ra_tls_attest_lib_(nullptr) {
    DoInitExpectedValues();
  }

  void DoInitExpectedValues();
  void DoInitVerification();
  void DoInitQuoteGeneration();
  void DoSetupSSLContext(boost::asio::ssl::context& ctx);

  X509* x509_cert_;
  uint8_t* der_key_;
  size_t der_key_size_;

  void* ra_tls_verify_lib_;
  void* ra_tls_attest_lib_;
};
}  // namespace seccask