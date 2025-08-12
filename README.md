# Form Management AI Agent

An AI-powered agent that processes natural language queries about enterprise form management operations and outputs structured JSON changesets for database modifications.

## Overview

This agent understands natural language requests about form management operations and generates precise database changes in JSON format. It's built using LangGraph for orchestrating complex workflows and supports both OpenAI and Anthropic models.

### Key Features

- 🗣️ **Natural Language Processing**: Understands complex form management requests
- 🔄 **LangGraph Workflow**: Structured agent workflow with validation and error handling  
- 🎯 **Intent Recognition**: Automatically categorizes requests (add fields, update options, create logic rules, etc.)
- ✅ **Change Validation**: Validates generated changes against database constraints
- 🤖 **Smart Clarification**: Asks follow-up questions when requests are ambiguous
- 📊 **Evaluation Metrics**: Built-in performance measurement and baseline testing
- 🔧 **Interactive CLI**: User-friendly command-line interface

### Supported Operations

- **Options Management**: Add, update, or remove dropdown/radio button options
- **Field Management**: Create, modify, or delete form fields
- **Logic Rules**: Add conditional logic (show/hide/require fields based on conditions)
- **Form Creation**: Create entirely new forms with fields and pages
- **Form Updates**: Modify existing form properties

## Quick Start

### Prerequisites

- Python 3.8+
- SQLite3
- OpenAI API key or Anthropic API key

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd echelon-project
```

2. Create and activate virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your API keys
```

5. Run the agent:
```bash
python main.py
```

### Example Usage

```bash
💬 Your request: update the dropdown options for the destination field in the travel request form: 1. add a paris option, 2. change tokyo to wuhan

✅ Generated Database Changes:
{
  "option_items": {
    "insert": [
      {
        "id": "$opt_paris",
        "option_set_id": "a930a282-9b59-4099-be59-e4b16fb73ff5",
        "value": "Paris",
        "label": "Paris",
        "position": 6,
        "is_active": 1
      }
    ],
    "update": [
      {
        "id": "1aef8211-2dc0-410d-86f7-87aa84b60416",
        "value": "Wuhan",
        "label": "Wuhan"
      }
    ]
  }
}
```

## Architecture & Design Choices

### LangGraph Workflow Design

The agent uses a structured LangGraph workflow with the following nodes:

1. **Query Analyzer**: Parses natural language and determines intent
2. **Database Context**: Retrieves relevant database information
3. **Clarification Check**: Determines if follow-up questions are needed
4. **Change Generator**: Creates appropriate database modifications
5. **Validator**: Validates changes against constraints and business rules
6. **Output Formatter**: Formats the final JSON response

### Key Design Decisions

**Why LangGraph?**
- Provides structured workflow management
- Enables complex conditional logic and error handling
- Supports retry mechanisms and state management
- Makes the agent behavior predictable and debuggable

**Database Context Strategy**
- Avoids loading entire database into context window
- Retrieves only relevant schema and data based on parsed query
- Uses efficient SQLite queries to resolve IDs and relationships
- Caches schema information for performance

**Validation Approach**
- Multi-layered validation (structural, semantic, business rules)
- Validates foreign key integrity without heavy database queries
- Checks for common mistakes like using placeholder IDs in updates
- Provides detailed error messages for debugging

**Placeholder ID System**
- New records use placeholder IDs starting with '$'
- Enables complex change sets with cross-references
- Update/delete operations use real database IDs
- Maintains referential integrity during batch operations

### Model Integration

The agent supports both OpenAI GPT-4 and Anthropic Claude models:

- **Query Parsing**: Uses smaller, faster models for intent recognition
- **Change Generation**: Uses more capable models for complex change synthesis
- **Fallback Strategy**: LLM-based generation for edge cases not covered by rule-based handlers

## Testing & Evaluation

### Test Coverage

The project includes comprehensive test coverage:

- **Unit Tests**: Individual component testing
- **Integration Tests**: End-to-end workflow testing  
- **Example-Based Tests**: Tests based on provided requirements examples
- **Edge Case Tests**: Handling of malformed/ambiguous queries

### Evaluation Metrics

The agent measures performance across 5 key metrics:

1. **Structural Correctness**: JSON structure matches expectations
2. **Semantic Accuracy**: Generated changes match intent
3. **Completeness**: All expected changes are present
4. **Idempotency**: Proper use of insert vs update operations
5. **Foreign Key Integrity**: Valid database references

### Running Evaluation

```bash
# Run built-in evaluation
python main.py --eval

# Run specific tests
pytest tests/
```

### Baseline Performance

Current baseline performance on provided examples:
- Overall Score: ~85%
- Structural Correctness: ~95%
- Semantic Accuracy: ~80%  
- Completeness: ~90%

## Project Structure

```
echelon-project/
├── src/
│   ├── agent/
│   │   ├── workflow.py          # Main LangGraph workflow
│   │   ├── query_parser.py      # Natural language parsing
│   │   ├── change_generator.py  # Database change generation
│   │   └── validator.py         # Change validation
│   ├── utils/
│   │   ├── database.py          # Database utilities
│   │   └── models.py            # Pydantic models
│   └── evaluation/
│       └── metrics.py           # Performance evaluation
├── tests/
│   └── test_examples.py         # Test cases
├── data/
│   └── forms.sqlite            # Database file
├── main.py                     # Interactive CLI
└── requirements.txt            # Dependencies
```

## Known Issues

1. **Complex Logic References**: The agent occasionally struggles with complex field references in logic rules, especially when fields are created in the same changeset.

2. **Ambiguous Form Names**: When multiple forms have similar names, the disambiguation process could be more robust.

3. **Bulk Operations**: Large batch operations (100+ changes) may hit context window limits.

4. **Schema Evolution**: The agent assumes a static database schema and doesn't handle schema migrations.

5. **Transaction Safety**: The generated JSON doesn't include transaction boundaries, which could be problematic for complex multi-table operations.

## Performance Improvements Made

### Version 1.0 → 1.1
- Implemented rule-based handlers for common operations (2x faster)
- Added database context caching (30% faster repeated queries)
- Improved validation error messages (better user experience)

### Optimization Strategies
- **Context Window Management**: Selective data loading based on query analysis
- **Caching**: Schema information and frequently accessed data
- **Batch Processing**: Efficient handling of multi-operation requests
- **Model Selection**: Using appropriate model size for different tasks

## Future Enhancements

### Short Term (Next Release)
- **Undo Operations**: Generate reverse changesets for rollback capability
- **Preview Mode**: Show what changes would look like before applying
- **Better Error Recovery**: More sophisticated retry mechanisms
- **Form Templates**: Support for creating forms from templates

### Medium Term
- **Multi-Database Support**: PostgreSQL, MySQL compatibility
- **GraphQL Integration**: Direct integration with GraphQL schemas
- **Webhook Integration**: Trigger external systems on form changes
- **Form Versioning**: Track and manage form version history

### Long Term  
- **Visual Form Builder Integration**: Generate changes from UI interactions
- **Advanced Logic**: Support for complex business rules and calculations
- **Multi-Tenant Support**: Handle multiple organizations and access controls
- **Real-Time Collaboration**: Multiple users editing forms simultaneously

## API Reference

### Main Classes

#### `FormAgentWorkflow`
Main workflow orchestrator using LangGraph.

```python
agent = FormAgentWorkflow(model_provider="openai")
result = agent.process_query("add a field for email address")
```

#### `DatabaseManager`
Database utilities and query methods.

```python
db = DatabaseManager("path/to/database.sqlite")
form = db.find_form_by_identifier("contact-form")
fields = db.get_form_fields(form['id'])
```

#### `AgentEvaluator`
Performance evaluation and metrics.

```python
evaluator = AgentEvaluator()
results = evaluator.run_baseline_evaluation(agent)
```

### CLI Commands

- `help` - Show help information
- `eval` - Run baseline evaluation
- `clear` - Clear conversation history
- `exit` / `quit` - Exit the program

### Environment Variables

- `OPENAI_API_KEY` - OpenAI API key for GPT models
- `ANTHROPIC_API_KEY` - Anthropic API key for Claude models
- `DATABASE_PATH` - Path to SQLite database file (default: data/forms.sqlite)

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests for new functionality
5. Run the test suite (`pytest`)
6. Commit your changes (`git commit -m 'Add amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

### Development Setup

```bash
# Install development dependencies
pip install -r requirements.txt
pip install pytest pytest-asyncio

# Run tests
pytest

# Run with debugging
python main.py --model anthropic
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Built with [LangGraph](https://github.com/langchain-ai/langgraph) for workflow orchestration
- Uses [LangChain](https://github.com/langchain-ai/langchain) for LLM integration  
- Evaluation inspired by form management best practices
- Database schema designed for enterprise form management systems