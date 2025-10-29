# # Install test dependencies
# pip install pytest pytest-asyncio pytest-cov pytest-mock

# # Run all tests
# pytest

# # Run specific test file
# pytest tests/test_qwen_processor.py

# # Run with coverage
# pytest --cov=source/agents --cov-report=html

# # Run only unit tests
# pytest -m unit

# # Run with verbose output
# pytest -vv

# # Run specific test
# pytest tests/test_qwen_processor.py::TestQwenProcessor::test_processor_initialization
# ```

# ---

# ## 📊 Expected Output
# ```
# ============== test session starts ==============
# collected 25 items

# tests/test_base_processor.py::TestBaseStreamProcessor::test_base_processor_is_abstract PASSED [  4%]
# tests/test_base_processor.py::TestBaseStreamProcessor::test_base_processor_subclass_creation PASSED [  8%]
# tests/test_qwen_processor.py::TestQwenCallback::test_callback_initialization PASSED [ 12%]
# tests/test_qwen_processor.py::TestQwenCallback::test_on_event_session_created PASSED [ 16%]
# tests/test_qwen_processor.py::TestQwenProcessor::test_processor_initialization PASSED [ 20%]
# ...

# ============== 25 passed in 2.5s ==============

# ---------- coverage: platform linux, python 3.11 ----------
# Name                                              Stmts   Miss  Cover
# ---------------------------------------------------------------------
# source/agents/base_processor.py                     150     10    93%
# source/agents/qwen_live_audio/qwen_live_audio_agent.py  200     15    92%
# ---------------------------------------------------------------------
# TOTAL                                               350     25    93%