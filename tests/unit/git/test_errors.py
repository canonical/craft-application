from craft_application.git import GitError


def test_git_error():
    """Test GitError."""
    git_error = GitError("Error details.")

    assert git_error.details == "Error details."
    assert str(git_error) == "Git operation failed."
    assert repr(git_error) == "GitError('Git operation failed.')"
