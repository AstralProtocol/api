"""Integration tests for database models."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Address, Chain, LocationProof, User


@pytest.mark.asyncio
async def test_user_crud(session: AsyncSession) -> None:
    """Test CRUD operations for User model."""
    # Create
    user = User(name="Test User", role="user")
    session.add(user)
    await session.commit()

    # Read
    stmt = select(User).where(User.name == "Test User")
    result = await session.execute(stmt)
    user_from_db = result.scalar_one()
    assert user_from_db.name == "Test User"
    assert user_from_db.role == "user"

    # Update
    user_from_db.role = "admin"
    await session.commit()
    stmt = select(User).where(User.id == user_from_db.id)
    result = await session.execute(stmt)
    updated_user = result.scalar_one()
    assert updated_user.role == "admin"

    # Delete
    await session.delete(user_from_db)
    await session.commit()
    stmt = select(User).where(User.id == user_from_db.id)
    result = await session.execute(stmt)
    assert result.first() is None


@pytest.mark.asyncio
async def test_chain_crud(session: AsyncSession) -> None:
    """Test CRUD operations for Chain model."""
    # Create
    chain = Chain(
        chain_id=1,
        name="Ethereum Mainnet",
        chain="ETH",
        rpc={"urls": ["https://mainnet.infura.io/v3/YOUR-PROJECT-ID"]},
        native_currency={
            "name": "Ether",
            "symbol": "ETH",
            "decimals": 18,
        },
        short_name="eth",
        network_id=1,
        icon="ethereum",
    )
    session.add(chain)
    await session.commit()

    # Read
    stmt = select(Chain).where(Chain.chain_id == 1)
    result = await session.execute(stmt)
    chain_from_db = result.scalar_one()
    assert chain_from_db.name == "Ethereum Mainnet"
    assert chain_from_db.chain == "ETH"

    # Update
    chain_from_db.rpc = {"urls": ["https://eth-mainnet.g.alchemy.com/v2/YOUR-API-KEY"]}
    await session.commit()
    stmt = select(Chain).where(Chain.chain_id == 1)
    result = await session.execute(stmt)
    updated_chain = result.scalar_one()
    assert updated_chain.rpc == {
        "urls": ["https://eth-mainnet.g.alchemy.com/v2/YOUR-API-KEY"]
    }

    # Delete
    await session.delete(chain_from_db)
    await session.commit()
    stmt = select(Chain).where(Chain.chain_id == 1)
    result = await session.execute(stmt)
    assert result.first() is None


@pytest.mark.asyncio
async def test_address_with_user_relationship(session: AsyncSession) -> None:
    """Test Address model with User relationship."""
    # Create user
    user = User(name="Test User", role="user")
    session.add(user)
    await session.commit()

    # Create address for user
    address = Address(
        user=user,
        address="0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
        is_verified=True,
    )
    session.add(address)
    await session.commit()

    # Test relationship from user to address
    user_stmt = (
        select(User).options(selectinload(User.addresses)).where(User.id == user.id)
    )
    user_result = await session.execute(user_stmt)
    user_from_db = user_result.scalar_one()
    assert len(user_from_db.addresses) == 1
    assert user_from_db.addresses[0].address == address.address

    # Test relationship from address to user
    address_stmt = (
        select(Address)
        .options(selectinload(Address.user))
        .where(Address.id == address.id)
    )
    address_result = await session.execute(address_stmt)
    address_from_db = address_result.scalar_one()
    assert address_from_db.user.id == user.id

    # Test cascade delete
    await session.delete(user)
    await session.commit()
    stmt = select(Address).where(Address.id == address.id)
    result = await session.execute(stmt)
    assert result.first() is None


@pytest.mark.asyncio
async def test_location_proof_relationships(session: AsyncSession) -> None:
    """Test LocationProof model with all its relationships."""
    # Create user
    user = User(name="Test User", role="user")
    session.add(user)
    await session.commit()

    # Create addresses with different addresses
    attester = Address(
        user=user,
        address="0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
        is_verified=True,
    )
    recipient = Address(
        user=user,
        address="0x742d35Cc6634C0532925a3b844Bc454e4438f44f",
        is_verified=True,
    )
    session.add_all([attester, recipient])
    await session.commit()

    # Create chain
    chain = Chain(
        chain_id=1,
        name="Ethereum Mainnet",
        chain="ETH",
        rpc={"urls": ["https://mainnet.infura.io/v3/YOUR-PROJECT-ID"]},
        native_currency={
            "name": "Ether",
            "symbol": "ETH",
            "decimals": 18,
        },
        short_name="eth",
        network_id=1,
        icon="ethereum",
    )
    session.add(chain)
    await session.commit()

    # Create location proof
    location_proof = LocationProof(
        schema_uid="0x456",
        attestation_uid="0x123",
        event_timestamp=1234567890,
        srs="EPSG:4326",
        spatial_type="point",
        location_wkt="POINT(0 0)",
        recipe_type="manual",
        recipe_payload={},
        media_type="none",
        media_data="none",
        status="onchain (validated)",
        chain=chain,
        attester=attester,
        recipient=recipient,
    )
    session.add(location_proof)
    await session.commit()

    # Test relationships
    stmt = (
        select(LocationProof)
        .options(
            selectinload(LocationProof.chain),
            selectinload(LocationProof.attester),
            selectinload(LocationProof.recipient),
        )
        .where(LocationProof.attestation_uid == "0x123")
    )
    result = await session.execute(stmt)
    proof_from_db = result.scalar_one()

    assert proof_from_db.chain.chain_id == chain.chain_id
    assert proof_from_db.attester.address == attester.address
    assert proof_from_db.recipient.address == recipient.address

    # Test reverse relationships
    chain_stmt = (
        select(Chain)
        .options(selectinload(Chain.location_proofs))
        .where(Chain.id == chain.id)
    )
    chain_result = await session.execute(chain_stmt)
    chain_from_db = chain_result.scalar_one()
    assert len(chain_from_db.location_proofs) == 1

    attester_stmt = (
        select(Address)
        .options(selectinload(Address.attested_proofs))
        .where(Address.id == attester.id)
    )
    attester_result = await session.execute(attester_stmt)
    attester_from_db = attester_result.scalar_one()
    assert len(attester_from_db.attested_proofs) == 1

    recipient_stmt = (
        select(Address)
        .options(selectinload(Address.received_proofs))
        .where(Address.id == recipient.id)
    )
    recipient_result = await session.execute(recipient_stmt)
    recipient_from_db = recipient_result.scalar_one()
    assert len(recipient_from_db.received_proofs) == 1

    # Test cascade delete
    await session.delete(chain)
    await session.commit()
    stmt = select(LocationProof).where(LocationProof.attestation_uid == "0x123")
    result = await session.execute(stmt)
    assert result.first() is None
