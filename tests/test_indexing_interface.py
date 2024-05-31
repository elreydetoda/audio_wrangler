import pytest

from models.db_models import FilesMetadata


def test_bulk_validation(session, example_file, faker):
    # Test for no match
    with pytest.raises(ValueError):
        session.db_obj.bulk_validate(session.session, [example_file])

    # Test for full match with the file in the database
    session.session.add(FilesMetadata(filename=str(example_file), processed=True))
    assert session.db_obj.bulk_validate(session.session, [example_file])

    # Test for partial match
    with pytest.raises(ValueError):
        session.db_obj.bulk_validate(
            session.session,
            [
                example_file,
                faker.file_path(
                    depth=2,
                    category="audio",
                    absolute=False,
                ),
            ],
        )
