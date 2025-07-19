from gitingest import ingest_async
import os
import aiofiles.os

async def git_tree_search(url):
    """
    Retrieves and returns the directory tree structure of a GitHub repository or a local Git repository.

    Args:
        url (str): The base URL of the GitHub repository (e.g., 'https://github.com/user/repo')
                   or the path to the local repository on your system.

    Returns:
        str: The directory tree structure as a string.
    """
    if not isinstance(url, str) or not url.strip():
        raise ValueError("The 'url' parameter must be a non-empty string.")

    # Check if it's a local path or a URL
    if os.path.exists(url):
        # It's a local path
        if not os.path.isdir(url):
            raise FileNotFoundError(f"The path '{url}' exists but is not a directory.")
    elif not url.startswith("http"):
        raise ValueError("Provided 'url' is neither a valid local path nor a valid URL.")

    try:
        summary, tree, content  = await ingest_async(url)
        return tree
    except Exception as e:
        raise Exception(f"Failed to retrieve the repo tree: {e}")
    
async def git_specific_content(base_url, part,type):
    """
    Fetches the content of a specific part (directory or file) from either:
    - a GitHub repository (via URL), or
    - a local Git repository (via local path).

    Args:
        base_url (str): The base URL of the GitHub repository (e.g., 'https://github.com/user/repo'),
                        or the local path to the root of the repository.
        part (str): The path inside the repository you wish to access (e.g., '/src/utils').

    Returns:
        str: The content of the specified part of the repository.
    """
    # Input validation
    if not isinstance(base_url, str) or not base_url.strip():
        raise ValueError("The 'base_url' parameter must be a non-empty string.")
    if not isinstance(part, str) or not part.strip():
        raise ValueError("The 'part' parameter must be a non-empty string.")

    # Check for local path
    if os.path.exists(base_url):
        # It's a local path
        repo_path = os.path.abspath(base_url)
        part_path = part.lstrip(os.sep)
        full_path = os.path.join(repo_path, part_path)
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"The specified part '{part}' does not exist in the local repository at '{base_url}'.")
        url_or_path = full_path
    else:
        # Assume it's a remote GitHub URL
        if not base_url.startswith("http"):
            raise ValueError("The 'base_url' must be a valid URL starting with 'http' or an existing local path.")
        base_url = base_url.rstrip('/')
        part = part if part.startswith('/') else '/' + part
        if type=='file':
            url_or_path = f"{base_url}/blob/main/{part}"
        elif type=='folder':
            url_or_path = f"{base_url}/tree/main/{part}"
        print(url_or_path)

    try:
        summary, tree, content = await ingest_async(url_or_path)
        return content
    except Exception as e:
        raise Exception(f"Failed to fetch content for '{url_or_path}': {e}")

async def folder_tree(
    path, level='broad-first', prefix='', cur_depth=1, max_depth=None
    ):
    """
    Async Markdown folder tree.

    Args:
        path (str): Root directory.
        level (str):
            - 'full': Show all folders and files, recursively, except hidden/system/cache entries.
            - 'broad-first': Only show immediate (top-level) folders and files (no nesting).
            - 'broad-second' or 'broad': Show top-level folders/files and their immediate child folders/files (two levels, no deeper).
        prefix (str): Indentation (internal)
        cur_depth (int): Current recursion depth (internal)
        max_depth (int): Max allowed depth (internal)
    Returns:
        str: Markdown tree string
    """
    def is_visible(entry):
        lower = entry.lower()
        hidden = entry.startswith('.')
        system = lower in ('desktop.ini', 'thumbs.db', '$recycle.bin', 'system volume information')
        cache = 'cache' in lower
        return not (hidden or system or cache)

    try:
        entries = await aiofiles.os.listdir(path)
        entries = sorted([e for e in entries if is_visible(e)])
    except FileNotFoundError:
        return f"{prefix}!! [Error: Folder not found]\n"
    except PermissionError:
        return f"{prefix}!! [Error: Permission denied]\n"
    except Exception as e:
        return f"{prefix}!! [Error: {str(e)}]\n"

    if max_depth is None:
        if level == 'broad-first':
            max_depth = 1
        elif level in ('broad-second', 'broad'):
            max_depth = 2
        else:
            max_depth = float('inf')

    tree_str = ""

    if level.startswith('broad'):
        # Separate folders and files
        folders = [e for e in entries if os.path.isdir(os.path.join(path, e))]
        files = [e for e in entries if os.path.isfile(os.path.join(path, e))]
        items = folders + files
    else:
        items = entries

    for idx, entry in enumerate(items):
        full_path = os.path.join(path, entry)
        is_last = idx == len(items) - 1
        connector = '└── ' if is_last else '├── '
        tree_str += f"{prefix}{connector}{entry}\n"
        if os.path.isdir(full_path) and not os.path.islink(full_path):
            if cur_depth < max_depth:
                extension = '    ' if is_last else '│   '
                try:
                    subtree = await folder_tree(
                        full_path,
                        level,
                        prefix + extension,
                        cur_depth=cur_depth + 1,
                        max_depth=max_depth,
                    )
                    tree_str += subtree
                except Exception as e:
                    tree_str += f"{prefix + extension}!! [Error: {str(e)}]\n"
    return tree_str