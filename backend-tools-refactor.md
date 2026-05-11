Refactor @backend/ai_generator.py to support sequential tool calling where Claude can make up to 2 tools calls in separate API rounds.

Current Behaviour:
- Claude makes 1 tool calls -> tools are removed from API params -> final response
- If Claude wants another tool call after seeing results, it can't (gets empty response)

Desire Behaviour:
- Each tool call should be a separate API request where Claude can resason about previous results
- Support for complex queries requiring multiple searches for comparisons, multi-part questions, or
  when information from different courses/lessons is needed

  Example flow:
  1. users: "Search for a course that discusses the same topic as lesson 4 of course X"
2. Claude: get course online for course X -> gets title of lesson 4
  3. Claude: uses the title to search for a course that discusses the same topic -> return course information
  4. Claude: provides complete answer

  Requirement:
  - Maximum 2 sequential rounds per user query
  - Terminate when: (a) 2 rounds completed, (b) Claude's response has no tool_use blocks, or (c) tool call fails
  - Preserve conversation context between rounds
  - Handle tool execution errors gracefully

  Notes:
  - update the system prompt in @backend/ai_generator.py
  - update the test @backend/tests/test_ai_generator.py
  - Write tests that verify the external behaviour (API calls made, tools executed, results returned) rather than internal state details.

  User two parallel subagents to brainstorm possible plans. Do not implement any code.
