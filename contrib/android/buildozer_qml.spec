[app]


title = Electrum


package.name = Electrum


package.domain = org.electrum


source.dir = .


source.include_exts = py,png,jpg,qml,qmltypes,ttf,txt,gif,pem,mo,json,csv,so,svg


source.exclude_exts = spec


source.exclude_dirs =
    bin,
    build,
    dist,
    contrib,
    env,
    tests,
    fastlane,
    electrum/www,
    electrum/scripts,
    electrum/utils,
    electrum/gui/qt,
    electrum/plugins/audio_modem,
    electrum/plugins/bitbox02,
    electrum/plugins/coldcard,
    electrum/plugins/digitalbitbox,
    electrum/plugins/jade,
    electrum/plugins/keepkey,
    electrum/plugins/ledger,
    electrum/plugins/nwc,
    electrum/plugins/payserver,
    electrum/plugins/revealer,
    electrum/plugins/safe_t,
    electrum/plugins/swapserver,
    electrum/plugins/timelock_recovery,
    electrum/plugins/trezor,
    electrum/plugins/watchtower,
    packages/qdarkstyle,
    packages/qtpy,
    packages/bin,
    packages/share,
    packages/pkg_resources,
    packages/setuptools


source.exclude_patterns = Makefile,setup*,

    packages/aiohttp-*.dist-info/*,
    packages/frozenlist-*.dist-info/*


version.regex = ELECTRUM_VERSION = '(.*)'
version.filename = %(source.dir)s/electrum/version.py






requirements =
    hostpython3,
    python3,
    android,
    openssl,
    plyer,
    libffi,
    libsecp256k1,
    cryptography,
    pyqt6sip,
    pyqt6,
    libzbar


presplash.filename = %(source.dir)s/electrum/gui/icons/electrum_presplash.png


icon.filename = %(source.dir)s/electrum/gui/icons/android_electrum_icon_legacy.png
icon.adaptive_foreground.filename = %(source.dir)s/electrum/gui/icons/android_electrum_icon_foreground.png
icon.adaptive_background.filename = %(source.dir)s/electrum/gui/icons/android_electrum_icon_background.png


orientation = portrait


fullscreen = False







android.permissions = INTERNET, CAMERA, WRITE_EXTERNAL_STORAGE, POST_NOTIFICATIONS



android.api = 31


android.target_sdk_version = 35


android.minapi = 23


android.ndk = 23b


android.ndk_api = 23





android.ndk_path = /opt/android/android-ndk


android.sdk_path = /opt/android/android-sdk


android.ant_path = /opt/android/apache-ant





android.skip_update = True





android.accept_sdk_license = True











android.add_jars = .buildozer/android/platform/*/build/libs_collections/Electrum/jar/*.jar


android.add_aars =
    contrib/android/.cache/aars/BarcodeScannerView.aar,
    contrib/android/.cache/aars/CameraView.aar,
    contrib/android/.cache/aars/zxing-cpp.aar




android.add_src = electrum/gui/qml/java_classes/


android.gradle_dependencies =
    com.android.support:support-compat:28.0.0,
    org.jetbrains.kotlin:kotlin-stdlib:1.8.22

android.add_activities = org.electrum.qr.SimpleScannerActivity











android.add_resources = electrum/gui/qml/android_res/layout:layout













android.manifest.intent_filters = contrib/android/bitcoin_intent.xml


android.manifest.launch_mode = singleTask























android.whitelist = lib-dynload/_csv.so


android.allow_backup = False


android.release_artifact = apk


android.debug_artifact = apk






p4a.source_dir = /opt/python-for-android


p4a.local_recipes = %(source.dir)s/contrib/android/p4a_recipes/





p4a.bootstrap = qt6


















[buildozer]


log_level = 2


bin_dir = ./dist






































