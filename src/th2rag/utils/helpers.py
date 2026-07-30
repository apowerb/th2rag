def construct_history(messages):
    role_mapping = {"USER": "user", "SYSTEM": "assistant"}

    history = [
        {"role": role_mapping.get(message.sender.name), "content": message.content}
        for message in messages
    ]

    return history


def build_script_generation_prompt(user_question: str, metadata: dict) -> str:
    shape = metadata.get("shape", [None, None])
    rows, cols = shape
    columns = metadata.get("columns", {})

    column_descriptions = "\n".join(f"- {col}: {dtype}" for col, dtype in columns.items())

    return f"""
    You are a data assistant. The user is working with a dataset with {rows} rows and {cols} columns.
    Here are the columns and their types:

    {column_descriptions}

    # Use the dataset as a variable named `dataset_value`.
    # Assume `dataset_value` is already defined and ready to use.
    # Inlcude all the used libraries in the begining of the script (library(library_name) syntax)
    # Do NOT include any code that reads or loads the dataset (e.g., `read_csv`, `read_excel`, etc.).
    # Do NOT assign anything to `dataset_value`. Assume it is already defined and ready to use.
    # Do NOT use any column not mentionned in the column descriptions.
    The user asked: "{user_question}"

    Please respond ONLY with a JSON object in this format:
    {{
    "script": "<r_script_string_using_dataset_value_directly>",
    "packages": ["<package1>", "<package2>"]
    }}

Do not include any explanation or text outside the JSON.
"""
