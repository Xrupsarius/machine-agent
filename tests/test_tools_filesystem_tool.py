import pytest
from pathlib import Path
from app.tools.filesystem_tool import FilesystemTool


@pytest.fixture
def tool():
    return FilesystemTool()


# --- create_file ---

def test_create_file_creates_file(tool, tmp_path):
    path = str(tmp_path / "test.txt")
    result = tool.execute("create_file", {"path": path, "content": "hello"})
    assert result.success
    assert Path(path).exists()
    assert Path(path).read_text() == "hello"


def test_create_file_empty_content(tool, tmp_path):
    path = str(tmp_path / "empty.txt")
    result = tool.execute("create_file", {"path": path})
    assert result.success
    assert Path(path).read_text() == ""


def test_create_file_no_path_fails(tool):
    result = tool.execute("create_file", {"path": ""})
    assert not result.success
    assert "No path" in result.error


def test_create_file_existing_fails(tool, tmp_path):
    path = str(tmp_path / "exists.txt")
    Path(path).write_text("original")
    result = tool.execute("create_file", {"path": path, "content": "new"})
    assert not result.success
    assert "already exists" in result.error


def test_create_file_nested_dirs(tool, tmp_path):
    path = str(tmp_path / "a" / "b" / "c.txt")
    result = tool.execute("create_file", {"path": path, "content": "deep"})
    assert result.success
    assert Path(path).exists()


def test_create_file_output_contains_path(tool, tmp_path):
    path = str(tmp_path / "out.txt")
    result = tool.execute("create_file", {"path": path})
    assert result.success
    assert path in result.output


# --- read_file ---

def test_read_file_reads_content(tool, tmp_path):
    path = str(tmp_path / "read.txt")
    Path(path).write_text("content here")
    result = tool.execute("read_file", {"path": path})
    assert result.success
    assert result.output == "content here"


def test_read_file_not_found(tool, tmp_path):
    result = tool.execute("read_file", {"path": str(tmp_path / "missing.txt")})
    assert not result.success
    assert "not found" in result.error.lower()


def test_read_file_no_path_fails(tool):
    result = tool.execute("read_file", {"path": ""})
    assert not result.success
    assert "No path" in result.error


def test_read_file_directory_fails(tool, tmp_path):
    result = tool.execute("read_file", {"path": str(tmp_path)})
    assert not result.success
    assert "Not a file" in result.error


def test_read_file_unicode(tool, tmp_path):
    path = str(tmp_path / "ru.txt")
    Path(path).write_text("Привет мир", encoding="utf-8")
    result = tool.execute("read_file", {"path": path})
    assert result.success
    assert result.output == "Привет мир"


# --- write_file ---

def test_write_file_creates_if_not_exists(tool, tmp_path):
    path = str(tmp_path / "new.txt")
    result = tool.execute("write_file", {"path": path, "content": "new content"})
    assert result.success
    assert Path(path).read_text() == "new content"


def test_write_file_overwrites(tool, tmp_path):
    path = str(tmp_path / "over.txt")
    Path(path).write_text("old")
    result = tool.execute("write_file", {"path": path, "content": "new"})
    assert result.success
    assert Path(path).read_text() == "new"


def test_write_file_no_path_fails(tool):
    result = tool.execute("write_file", {"path": ""})
    assert not result.success
    assert "No path" in result.error


def test_write_file_nested_dirs(tool, tmp_path):
    path = str(tmp_path / "x" / "y" / "z.txt")
    result = tool.execute("write_file", {"path": path, "content": "deep"})
    assert result.success
    assert Path(path).read_text() == "deep"


# --- append_file ---

def test_append_file_appends(tool, tmp_path):
    path = str(tmp_path / "append.txt")
    Path(path).write_text("first\n")
    result = tool.execute("append_file", {"path": path, "content": "second\n"})
    assert result.success
    assert Path(path).read_text() == "first\nsecond\n"


def test_append_file_creates_if_not_exists(tool, tmp_path):
    path = str(tmp_path / "appnew.txt")
    result = tool.execute("append_file", {"path": path, "content": "line"})
    assert result.success
    assert Path(path).read_text() == "line"


def test_append_file_no_path_fails(tool):
    result = tool.execute("append_file", {"path": ""})
    assert not result.success
    assert "No path" in result.error


def test_append_file_multiple_times(tool, tmp_path):
    path = str(tmp_path / "multi.txt")
    tool.execute("append_file", {"path": path, "content": "a"})
    tool.execute("append_file", {"path": path, "content": "b"})
    tool.execute("append_file", {"path": path, "content": "c"})
    assert Path(path).read_text() == "abc"


# --- delete_file ---

def test_delete_file_removes_file(tool, tmp_path):
    path = str(tmp_path / "del.txt")
    Path(path).write_text("bye")
    result = tool.execute("delete_file", {"path": path})
    assert result.success
    assert not Path(path).exists()


def test_delete_file_not_found(tool, tmp_path):
    result = tool.execute("delete_file", {"path": str(tmp_path / "missing.txt")})
    assert not result.success
    assert "not found" in result.error.lower()


def test_delete_file_no_path_fails(tool):
    result = tool.execute("delete_file", {"path": ""})
    assert not result.success
    assert "No path" in result.error


def test_delete_directory_fails(tool, tmp_path):
    result = tool.execute("delete_file", {"path": str(tmp_path)})
    assert not result.success
    assert "Not a file" in result.error


# --- list_dir ---

def test_list_dir_lists_files(tool, tmp_path):
    (tmp_path / "a.txt").write_text("")
    (tmp_path / "b.txt").write_text("")
    result = tool.execute("list_dir", {"path": str(tmp_path)})
    assert result.success
    assert "a.txt" in result.output
    assert "b.txt" in result.output


def test_list_dir_empty_dir(tool, tmp_path):
    d = tmp_path / "empty"
    d.mkdir()
    result = tool.execute("list_dir", {"path": str(d)})
    assert result.success
    assert "(empty)" in result.output


def test_list_dir_path_not_found(tool, tmp_path):
    result = tool.execute("list_dir", {"path": str(tmp_path / "nope")})
    assert not result.success
    assert "not found" in result.error.lower()


def test_list_dir_on_file_fails(tool, tmp_path):
    f = tmp_path / "f.txt"
    f.write_text("")
    result = tool.execute("list_dir", {"path": str(f)})
    assert not result.success
    assert "Not a directory" in result.error


def test_list_dir_marks_subdirs(tool, tmp_path):
    (tmp_path / "subdir").mkdir()
    result = tool.execute("list_dir", {"path": str(tmp_path)})
    assert result.success
    assert "D " in result.output


def test_list_dir_default_path(tool):
    result = tool.execute("list_dir", {})
    assert result.success


# --- search_files ---

def test_search_files_finds_match(tool, tmp_path):
    (tmp_path / "foo.txt").write_text("")
    (tmp_path / "bar.txt").write_text("")
    result = tool.execute("search_files", {"path": str(tmp_path), "pattern": "*.txt"})
    assert result.success
    assert "foo.txt" in result.output


def test_search_files_recursive(tool, tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "deep.log").write_text("")
    result = tool.execute("search_files", {"path": str(tmp_path), "pattern": "*.log"})
    assert result.success
    assert "deep.log" in result.output


def test_search_files_no_match(tool, tmp_path):
    result = tool.execute("search_files", {"path": str(tmp_path), "pattern": "*.xyz"})
    assert result.success
    assert "No files found" in result.output


def test_search_files_path_not_found(tool, tmp_path):
    result = tool.execute("search_files", {"path": str(tmp_path / "missing"), "pattern": "*"})
    assert not result.success
    assert "not found" in result.error.lower()


def test_search_files_default_pattern(tool, tmp_path):
    (tmp_path / "any.txt").write_text("")
    result = tool.execute("search_files", {"path": str(tmp_path)})
    assert result.success
    assert "any.txt" in result.output


# --- unknown action ---

def test_unknown_action_fails(tool):
    result = tool.execute("teleport", {})
    assert not result.success
    assert "teleport" in result.error


# --- tool properties and metadata ---

def test_name():
    assert FilesystemTool().name == "filesystem"


def test_description():
    assert len(FilesystemTool().description) > 5


def test_execute_sets_tool_name(tool, tmp_path):
    path = str(tmp_path / "meta.txt")
    result = tool.execute("create_file", {"path": path})
    assert result.tool_name == "filesystem"


def test_execute_sets_action(tool, tmp_path):
    path = str(tmp_path / "meta2.txt")
    result = tool.execute("create_file", {"path": path})
    assert result.action == "create_file"
