"""ReplayLens Canary: scheduled drift checks for LLM provider endpoints.

Runs a small, public eval set on a schedule, grades it deterministically,
and flags statistically significant changes against a frozen baseline.
"""
