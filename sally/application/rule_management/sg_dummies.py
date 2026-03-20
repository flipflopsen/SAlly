"""
Dummy implementations - DEPRECATED.

This module redirects to the legacy versions for backward compatibility.
Use the full implementations in sg_rule.py and sg_rule_manager.py instead.

Migration:
- DummySmartGridRule -> SmartGridRule from sally.application.rule_management.sg_rule
- DummySmartGridRuleManager -> SmartGridRuleManager from sally.application.rule_management.sg_rule_manager
"""
import warnings

# Redirect to legacy module
from sally.legacy.sg_dummies import DummySmartGridRule, DummySmartGridRuleManager

__all__ = ['DummySmartGridRule', 'DummySmartGridRuleManager']

# Issue deprecation warning on import
warnings.warn(
    "sally.application.rule_management.sg_dummies is deprecated. "
    "Use SmartGridRule and SmartGridRuleManager instead.",
    DeprecationWarning,
    stacklevel=2
)
