"""EXT (实时配音桥接 + Chrome 插件) 版本号——桥接窗口标题、bridge.log、插件 manifest 共用。
改版本时同时改 extension/manifest.json 的 "version"。"""
EXT_VERSION = "0.4.23"
EXT_BUILD_DATE = "2026-11-26"


def version_label() -> str:
    return "v%s（%s）" % (EXT_VERSION, EXT_BUILD_DATE)
