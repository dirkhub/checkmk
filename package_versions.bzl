# TODO: Duplicated from defines.make:
# we need to centralize this again as soon as the whole build process is migrated to bazel.
PYTHON_VERSION = "3.11.5"
PYTHON_VERSION_ARRAY = PYTHON_VERSION.split(".")
PYTHON_VERSION_MAJOR = PYTHON_VERSION_ARRAY[0]
PYTHON_VERSION_MINOR = PYTHON_VERSION_ARRAY[1]
PYTHON_MAJOR_DOT_MINOR = "%s.%s" % (PYTHON_VERSION_MAJOR, PYTHON_VERSION_MINOR)
PYTHON_SHA256 = "85cd12e9cf1d6d5a45f17f7afe1cebe7ee628d3282281c492e86adf636defa3f"

PATCH_VERSION = "2.7.6"
PATCH_SHA256 = "8cf86e00ad3aaa6d26aca30640e86b0e3e1f395ed99f189b06d4c9f74bc58a4e"

REDIS_VERSION = "6.2.6"
REDIS_SHA256 = "5b2b8b7a50111ef395bf1c1d5be11e6e167ac018125055daa8b5c2317ae131ab"

OPENSSL_VERSION = "3.0.11"
OPENSSL_SHA256 = "b3425d3bb4a2218d0697eb41f7fc0cdede016ed19ca49d168b78e8d947887f55"

XMLSEC1_VERSION = "1.2.37"
XMLSEC1_SHA256 = "5f8dfbcb6d1e56bddd0b5ec2e00a3d0ca5342a9f57c24dffde5c796b2be2871c"

HEIRLOOMMAILX_VERSION = "12.5"
HEIRLOOMMAILX_SHA256 = "015ba4209135867f37a0245d22235a392b8bbed956913286b887c2e2a9a421ad"

MONITORING_PLUGINS_VERSION = "2.3.3"
MONITORING_PLUGINS_SHA256 = "7023b1dc17626c5115b061e7ce02e06f006e35af92abf473334dffe7ff3c2d6d"

STUNNEL_VERSION = "5.63"
STUNNEL_SHA256 = "c74c4e15144a3ae34b8b890bb31c909207301490bd1e51bfaaa5ffeb0a994617"

FREETDS_VERSION = "0.95.95"
FREETDS_SHA256 = "be7c90fc771f30411eff6ae3a0d2e55961f23a950a4d93c44d4c488006e64c70"

HEIRLOOM_PKGTOOLS_VERSION = "070227"
HEIRLOOM_PKGTOOLS_SHA256 = "aa94d33550847d57c62138cabd0f742d4af2f14aa2bfb9e9d4a9427bf498e6cc"

LIBGSF_VERSION = "1.14.44"
LIBGSF_SHA256 = "68bede10037164764992970b4cb57cd6add6986a846d04657af9d5fac774ffde"

LCAB_VERSION = "1.0b12"
LCAB_SHA256 = "065f2c1793b65f28471c0f71b7cf120a7064f28d1c44b07cabf49ec0e97f1fc8"

MSITOOLS_VERSION = "0.94"
MSITOOLS_SHA256 = "ebbdd9aa714a6a6ada4450aff5e86351cf910d09b24a85645425737602d75df5"

SNAP7_VERSION = "1.4.2"
SNAP7_SHA256 = "fe137737b432d95553ebe5d5f956f0574c6a80c0aeab7a5262fb36b535df3cf4"

NRPE_VERSION = "3.2.1"
NRPE_SHA256 = "8ad2d1846ab9011fdd2942b8fc0c99dfad9a97e57f4a3e6e394a4ead99c0f1f0"

MOD_FCGID_VERSION = "2.3.9"
MOD_FCGID_SHA256 = "1cbad345e3376b5d7c8f9a62b471edd7fa892695b90b79502f326b4692a679cf"

XINETD_VERSION = "2.3.15.4"
XINETD_SHA256 = "2baa581010bc70361abdfa37f121e92aeb9c5ce67f9a71913cebd69359cc9654"

NAGIOS_VERSION = "3.5.1"
NAGIOS_SHA256 = "b4323f8c027bf3f409225eeb4f7fb8e55856092ef5f890206fc2983bc75b072e"

PNP4NAGIOS_VERSION = "0.6.26"
PNP4NAGIOS_SHA256 = "ab59a8a02d0f70de3cf89b12fe1e9216e4b1127bc29c04a036cd06dde72ee8fb"

CRYPT_SSL_VERSION = "0.72"
CRYPT_SSL_SHA256 = "f5d34f813677829857cf8a0458623db45b4d9c2311daaebe446f9e01afa9ffe8"

MOD_WSGI_VERSION = "4.9.4"
MOD_WSGI_SHA256 = "ee926a3fd5675890b908ebc23db1f8f7f03dc3459241abdcf35d46c68e1be29b"

NET_SNMP_VERSION = "5.9.1"
NET_SNMP_SHA256 = "ddbe4d0111a0f1fb4c29751b2794d618565557facdda5315786f0a22472499d3"
