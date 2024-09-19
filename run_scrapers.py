import importlib
import os

def run_all_scrapers():
    scraper_dir = 'scripts'
    excluded_files = ['config.py']  # Add any other files you want to exclude
    for filename in os.listdir(scraper_dir):
        if filename.startswith('update_') and filename.endswith('.py') and filename not in excluded_files:
            module_name = filename[:-3]
            module = importlib.import_module(f'scripts.{module_name}')
            if hasattr(module, 'main'):
                module.main()

if __name__ == "__main__":
    run_all_scrapers()