class KernelError(Exception):
    code = "KERNEL_ERROR"


class ContractValidationError(KernelError):
    code = "CONTRACT_VALIDATION"


class TimestampValidationError(ContractValidationError):
    code = "INVALID_TIMESTAMP"


class DecimalValidationError(ContractValidationError):
    code = "INVALID_DECIMAL"


class OrderIdentityError(ContractValidationError):
    code = "ORDER_IDENTITY"


class UnknownOrderStateError(KernelError):
    code = "UNKNOWN_ORDER_STATE"


class ReadinessDeniedError(KernelError):
    code = "READINESS_DENIED"


class IsolationViolationError(KernelError):
    code = "ISOLATION_VIOLATION"
