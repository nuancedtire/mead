import importlib
import os

def run_all_scrapers():
    scraper_dir = 'scripts'
    excluded_files = ['base_scraper.py', 'config.py']  # Exclude update_.py and config.py
    
    # Run update_*.py scripts
    for filename in os.listdir(scraper_dir):
        if filename.startswith('update_') and filename.endswith('.py') and filename not in excluded_files:
            module_name = filename[:-3]
            module = importlib.import_module(f'scripts.{module_name}')
            if hasattr(module, 'main'):
                print(f"Running {filename}")
                module.main()
    
    # Run llm.py
    llm_module = importlib.import_module('scripts.llm')
    if hasattr(llm_module, 'main'):
        print("Running llm.py")
        llm_module.main()

if __name__ == "__main__":
    run_all_scrapers()