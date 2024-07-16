from craft_application.git import errors


def test_git_error():
    """Test GitError."""
    error = errors.GitError("Error details.")

    assert error.details == "Error details."
    assert str(error) == "Git operation failed."
    assert repr(error) == "GitError('Git operation failed.')"
