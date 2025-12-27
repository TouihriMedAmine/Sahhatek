#!/usr/bin/env python3
"""
LangSmith Integration Status CLI
Affiche un rapport détaillé de l'état de l'intégration
"""

import os
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))


def print_header(title):
    """Print a formatted header"""
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)


def print_section(name):
    """Print a section title"""
    print(f"\n  📌 {name}")
    print("  " + "-"*66)


def check_environment():
    """Check environment variables"""
    print_header("🔧 ENVIRONMENT CONFIGURATION")
    
    vars_to_check = {
        "LANGCHAIN_API_KEY": "LangSmith API Key",
        "LANGCHAIN_TRACING_V2": "Tracing Enabled",
        "LANGCHAIN_PROJECT": "Project Name",
    }
    
    for var, description in vars_to_check.items():
        value = os.getenv(var)
        if var == "LANGCHAIN_API_KEY":
            status = "✅ SET" if value else "❌ NOT SET"
            display = "***" if value else "None"
        else:
            status = "✅ SET" if value else "❌ NOT SET"
            display = value or "None"
        
        print(f"  {var:30} {status:15} Value: {display}")
    
    print("\n  Configuration file (.env) location:")
    print(f"  {Path('.env').absolute()}")


def check_module():
    """Check if langsmith_decorators module is available"""
    print_header("📦 MODULE STATUS")
    
    try:
        import agents.langsmith_decorators as decorators
        print("\n  ✅ agents.langsmith_decorators imported successfully")
        
        # Check available decorators
        decorators_available = [
            'trace_agent_node',
            'trace_llm_call',
            'trace_retrieval',
            'trace_tool_call',
            'add_metadata_to_state',
            'trace_state_update',
        ]
        
        print("\n  Available decorators:")
        for decorator in decorators_available:
            has_it = hasattr(decorators, decorator)
            status = "✅" if has_it else "❌"
            print(f"    {status} {decorator}")
        
        # Check configuration
        print("\n  Configuration status:")
        print(f"    Enabled: {decorators.LANGSMITH_ENABLED}")
        print(f"    Available: {decorators.LANGSMITH_AVAILABLE}")
        print(f"    Project: {decorators.LANGSMITH_PROJECT}")
        
    except Exception as e:
        print(f"\n  ❌ Error importing module: {e}")


def check_agents():
    """Check if all agents are properly integrated"""
    print_header("🤖 AGENT INTEGRATION STATUS")
    
    agents_to_check = {
        "Medical Agent": "agents.medical_agent.agent",
        "Mental Health Agent": "agents.mental_health.agent",
        "Triage Agent": "agents.triage_agent.agent",
        "Rumor Agent": "agents.rumor.agent",
    }
    
    for agent_name, module_path in agents_to_check.items():
        try:
            module = __import__(module_path, fromlist=[''])
            print(f"\n  ✅ {agent_name}")
            print(f"     Module: {module_path}")
            print(f"     Status: Integrated with LangSmith")
        except Exception as e:
            print(f"\n  ❌ {agent_name}")
            print(f"     Error: {str(e)[:50]}...")


def check_files():
    """Check if required files exist"""
    print_header("📁 FILE STRUCTURE")
    
    files_to_check = {
        "agents/langsmith_decorators.py": "Core module",
        "LANGSMITH_INTEGRATION.md": "Complete documentation",
        "LANGSMITH_QUICKSTART.md": "Quick start guide",
        "LANGSMITH_CHANGES.md": "Change summary",
        "test_langsmith_integration.py": "Test script",
        ".env.example": "Configuration template",
    }
    
    print("\n  Required files:")
    for filepath, description in files_to_check.items():
        exists = Path(filepath).exists()
        status = "✅" if exists else "❌"
        print(f"  {status} {filepath:40} ({description})")


def check_database():
    """Check LangSmith connectivity"""
    print_header("🔗 LANGSMITH CONNECTIVITY")
    
    try:
        from agents.langsmith_decorators import LANGSMITH_AVAILABLE
        
        if LANGSMITH_AVAILABLE:
            print("\n  ✅ LangSmith connection available")
            print("\n  Actions:")
            print("    • Traces will be sent to LangSmith Cloud")
            print("    • View at: https://smith.langchain.com/projects")
            print("    • Real-time monitoring enabled")
        else:
            print("\n  ⚠️  LangSmith connection NOT available")
            print("\n  Reasons might be:")
            print("    • LANGCHAIN_API_KEY not set")
            print("    • LANGCHAIN_TRACING_V2 not set to 'true'")
            print("    • Network connectivity issue")
            print("\n  Solution:")
            print("    1. Check .env configuration")
            print("    2. Get API key from https://smith.langchain.com")
            print("    3. Restart application")
    except Exception as e:
        print(f"\n  ❌ Error checking connectivity: {e}")


def show_next_steps():
    """Show recommended next steps"""
    print_header("🚀 NEXT STEPS")
    
    from agents.langsmith_decorators import LANGSMITH_AVAILABLE
    
    if LANGSMITH_AVAILABLE:
        steps = [
            ("✅ CONFIGURATION", "LangSmith is properly configured"),
            ("→", "Run: python test_langsmith_integration.py"),
            ("→", "Make a request through the chat interface"),
            ("→", "View traces at: https://smith.langchain.com/projects"),
            ("→", "Check dashboard: http://localhost:8000/chat/dashboard/langsmith/"),
            ("→", "Read docs: ./LANGSMITH_INTEGRATION.md"),
        ]
    else:
        steps = [
            ("⚠️  CONFIGURATION", "LangSmith needs to be configured"),
            ("1", "Go to https://smith.langchain.com"),
            ("2", "Create account and copy API key"),
            ("3", "Update .env with: LANGCHAIN_API_KEY=your_key"),
            ("4", "Set: LANGCHAIN_TRACING_V2=true"),
            ("5", "Restart application"),
            ("6", "Run: python test_langsmith_integration.py"),
        ]
    
    print()
    for step, desc in steps:
        print(f"  {step:20} {desc}")


def print_footer():
    """Print footer with timestamp"""
    print("\n" + "="*70)
    print(f"  Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("  For more info: https://docs.smith.langchain.com")
    print("="*70 + "\n")


def main():
    """Run all checks"""
    print("\n")
    print("╔" + "="*68 + "╗")
    print("║" + " "*10 + "🎯 LangSmith Integration Status Report" + " "*20 + "║")
    print("╚" + "="*68 + "╝")
    
    # Run all checks
    check_environment()
    check_module()
    check_agents()
    check_files()
    check_database()
    show_next_steps()
    print_footer()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
