"""
Utility module for flexible value comparisons in test configurations.
"""

class ValueValidator:
    """Base class for value validators"""
    def validate(self, actual_value):
        """
        Validate the actual value against the expected criteria.
        
        Args:
            actual_value: The value to validate
            
        Returns:
            tuple: (is_valid, error_message)
        """
        raise NotImplementedError("Subclasses must implement validate()")
    
    @staticmethod
    def create(spec):
        """
        Factory method to create the appropriate validator based on the spec.
        
        Args:
            spec: The specification which can be one of:
                - direct value (for equality comparison)
                - dict with operator keys
                - None (to check for non-existence)
                
        Returns:
            ValueValidator: An instance of the appropriate validator
        """
        if spec is None:
            return NoneValidator()
        elif isinstance(spec, dict) and any(k in spec for k in ['eq', 'gt', 'lt', 'ge', 'le', 'range', 'approx']):
            if 'range' in spec:
                return RangeValidator(spec['range'][0], spec['range'][1])
            elif 'eq' in spec:
                return EqualityValidator(spec['eq'])
            elif 'gt' in spec:
                return GreaterThanValidator(spec['gt'])
            elif 'lt' in spec:
                return LessThanValidator(spec['lt'])
            elif 'ge' in spec:
                return GreaterThanOrEqualValidator(spec['ge'])
            elif 'le' in spec:
                return LessThanOrEqualValidator(spec['le'])
            elif 'approx' in spec:
                return ApproximateValidator(spec['approx'])
        else:
            # Default to equality for direct values
            return EqualityValidator(spec)


class EqualityValidator(ValueValidator):
    """Validates that a value equals the expected value"""
    def __init__(self, expected_value):
        self.expected_value = expected_value
        
    def validate(self, actual_value):
        is_valid = actual_value == self.expected_value
        error_msg = None if is_valid else f"expected '{self.expected_value}', got '{actual_value}'"
        return is_valid, error_msg


class GreaterThanValidator(ValueValidator):
    """Validates that a value is greater than the expected value"""
    def __init__(self, min_value):
        self.min_value = min_value
        
    def validate(self, actual_value):
        is_valid = actual_value > self.min_value
        error_msg = None if is_valid else f"expected > {self.min_value}, got {actual_value}"
        return is_valid, error_msg


class LessThanValidator(ValueValidator):
    """Validates that a value is less than the expected value"""
    def __init__(self, max_value):
        self.max_value = max_value
        
    def validate(self, actual_value):
        is_valid = actual_value < self.max_value
        error_msg = None if is_valid else f"expected < {self.max_value}, got {actual_value}"
        return is_valid, error_msg


class GreaterThanOrEqualValidator(ValueValidator):
    """Validates that a value is greater than or equal to the expected value"""
    def __init__(self, min_value):
        self.min_value = min_value
        
    def validate(self, actual_value):
        is_valid = actual_value >= self.min_value
        error_msg = None if is_valid else f"expected >= {self.min_value}, got {actual_value}"
        return is_valid, error_msg


class LessThanOrEqualValidator(ValueValidator):
    """Validates that a value is less than or equal to the expected value"""
    def __init__(self, max_value):
        self.max_value = max_value
        
    def validate(self, actual_value):
        is_valid = actual_value <= self.max_value
        error_msg = None if is_valid else f"expected <= {self.max_value}, got {actual_value}"
        return is_valid, error_msg


class ApproximateValidator(ValueValidator):
    """Validates that a value is approximately equal to the expected value (within ±0.1)"""
    def __init__(self, expected_value):
        self.expected_value = expected_value
        self.tolerance = 0.11
        
    def validate(self, actual_value):
        is_valid = abs(actual_value - self.expected_value) <= self.tolerance
        error_msg = None if is_valid else f"expected approximately {self.expected_value} (±{self.tolerance}), got {actual_value}"
        return is_valid, error_msg


class RangeValidator(ValueValidator):
    """Validates that a value is within a specified range (inclusive)"""
    def __init__(self, min_value, max_value):
        self.min_value = min_value
        self.max_value = max_value
        
    def validate(self, actual_value):
        is_valid = self.min_value <= actual_value <= self.max_value
        error_msg = None if is_valid else f"expected value between {self.min_value} and {self.max_value}, got {actual_value}"
        return is_valid, error_msg


class NoneValidator(ValueValidator):
    """Validates that a value is None or doesn't exist"""
    def validate(self, actual_value):
        is_valid = actual_value is None
        error_msg = None if is_valid else f"expected None, got {actual_value}"
        return is_valid, error_msg
