def string_to_html_div(input_string):
    if not isinstance(input_string, str):
        raise ValueError("Input must be a string")

    # Replace newlines with <br> tags
    html_content = input_string.replace("\n", "<br>")

    # Wrap the content in a div
    html_div = f"<div>{html_content}</div>"

    return html_div


def convert_string_to_html(raw_string):
    # Convert special HTML characters to their escape sequences
    escaped_string = (
        raw_string.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#039;")
    )

    # Replace newline characters with <br> tags
    html_string = escaped_string.replace("\n", "<br>\n")

    # Wrap the escaped string in a <div> tag
    html_output = f"<div>{html_string}</div>"

    return html_output