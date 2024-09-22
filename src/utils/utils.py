def string_to_html_div(input_string):
    if not isinstance(input_string, str):
        raise ValueError("Input must be a string")

    # Replace newlines with <br> tags
    html_content = input_string.replace("\n", "<br>")

    # Wrap the content in a div
    html_div = f"<div>{html_content}</div>"

    return html_div
