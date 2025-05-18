class LINError(Exception):
    """Base LIN protocol exception"""
    pass

class LINChecksumError(LINError):
    """Checksum verification failed"""
    pass

class LINParityError(LINError):
    """PID parity check failed"""
    pass

class LINSyncError(LINError):
    """Sync byte mismatch"""
    pass

class LINFrameError(LINError):
    """Frame structure error"""
    pass