from settingsconfig.utils import DEFAULT_SETTINGS, get_setting


def system_settings(request):
    data = {key: get_setting(key, default=value) for key, value in DEFAULT_SETTINGS.items()}
    return {'SYSTEM_SETTINGS': data}
