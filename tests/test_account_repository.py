from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Base
from app.repositories.accounts import AccountRepository


def test_account_repository_crud() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        repo = AccountRepository(session)
        account = repo.create(
            service_name="GitHub",
            account_label="Work",
            issuer="GitHub",
            encrypted_secret="encrypted",
        )
        session.commit()

        assert repo.count() == 1
        assert repo.get(account.id).service_name == "GitHub"
        assert len(repo.search("work")) == 1

        repo.rename(account, "GitHub", "Personal")
        assert repo.get(account.id).account_label == "Personal"

        repo.delete(account)
        session.commit()
        assert repo.count() == 0

