import json
import os

def run_ainx_workflow(json_path):
    with open(json_path, "r") as f:
        workflow = json.load(f)

    content = workflow.get("content", {})
    page_name = content.get("page_name", "ainx_page")
    components = content.get("components", [])
    target_dir = workflow["context"].get("target_dir", "apps/")

    os.makedirs(target_dir, exist_ok=True)
    page_file = os.path.join(target_dir, f"{page_name}.py")

    with open(page_file, "w") as f:
        f.write("import reflex as rx\n\n")
        f.write(f"def {page_name}():\n")
        for c in components:
            f.write(f"    yield rx.{c['type']}({json.dumps(c['props'])})\n")

    print(f"[✅] Page created at: {page_file}")

if __name__ == "__main__":
    run_ainx_workflow("workflow.json")
