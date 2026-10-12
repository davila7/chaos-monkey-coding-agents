class LedgerError(Exception):
    pass


class FormatError(LedgerError):
    pass


class MissingRate(LedgerError):
    pass


class UnmatchedReversal(LedgerError):
    pass
