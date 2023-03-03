class FtpSettings:
    def __init__(self, host: str,
                 tftp_folder: str,
                 templates_initial_path: str,
                 templates_full_path: str,
                 configs_initial_path: str,
                 configs_full_path: str,
                 firmwares_path: str):
        self.host = host
        self.tftp_folder = tftp_folder
        self.templates_initial_path = templates_initial_path
        self.templates_full_path = templates_full_path
        self.configs_initial_path = configs_initial_path
        self.configs_full_path = configs_full_path
        self.firmwares_path = firmwares_path
