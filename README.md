# Decentralized Identity System

A blockchain-backed decentralized identity authentication system designed for **untrusted off-chain storage environments**.

The system stores complete DID documents off-chain while anchoring critical state summaries on blockchain. By combining document hashing, Merkle Trees, version-chain verification, selective attribute proofs, and data recovery mechanisms, the system can detect and recover from DID document tampering, rollback, and deletion.

> This project was developed as part of my undergraduate graduation project on decentralized identity authentication and blockchain-based data integrity protection.

---

## Overview

Traditional decentralized identity systems often store DID documents outside the blockchain because storing complete identity data on-chain is expensive and may introduce privacy concerns.

However, off-chain storage introduces another problem:

> What happens if the storage environment itself cannot be trusted?

An attacker or faulty storage service may:

- modify a DID document;
- replace it with an older version;
- delete identity data;
- return inconsistent identity information.

This project addresses these problems by separating **trusted state verification** from **off-chain data storage**.

The blockchain stores compact DID state summaries, while MongoDB stores the complete DID documents and related records.

When a DID document is retrieved, the backend reconstructs its cryptographic state and compares it with the blockchain anchor to determine whether the off-chain data remains trustworthy.

---

## Key Features

### Decentralized Identity Lifecycle

The system implements the major operations required for managing decentralized identities:

```text
Register → Query → Update → Verify → Proof → Recover
```

Users can register new decentralized identities, update DID documents, verify their integrity, generate attribute-level proofs, and recover damaged identity data.

### Blockchain State Anchoring

Instead of storing the complete DID document on-chain, the system records compact cryptographic state information on blockchain.

The anchored state includes information such as:

```text
DID
 │
 ├── Version
 ├── Document Hash
 ├── Merkle Root
 └── Version Hash
```

This design reduces blockchain storage overhead while preserving a trusted reference for integrity verification.

### DID Document Integrity Verification

The system calculates cryptographic hashes for DID documents and compares them with blockchain state.

This makes it possible to detect unauthorized modification of off-chain identity data.

```text
Off-chain DID Document
        │
        ▼
   Hash Calculation
        │
        ▼
Blockchain State Anchor
        │
        ▼
 Match / Mismatch
```

### Version and Rollback Detection

DID updates generate new document states and version information.

The version relationship can be verified against blockchain records, allowing the system to detect situations where an attacker replaces the latest DID document with an older but otherwise valid version.

### Attribute-Level Merkle Proof

The system supports Merkle Tree based selective verification.

Instead of revealing an entire DID document, a verifier can validate an individual identity attribute using a Merkle Proof.

For example:

```text
DID Document
├── publicKey
├── controller
├── organization   ← attribute to verify
└── service
        │
        ▼
    Merkle Proof
        │
        ▼
    Merkle Root
        │
        ▼
Blockchain Anchor
```

This provides a foundation for privacy-preserving and selective identity verification.

### DID Recovery

The system includes recovery mechanisms for situations where off-chain DID data is corrupted or deleted.

Recovery strategies include:

* multi-replica data recovery;
* XOR-based erasure coding;
* recovery block reconstruction.

Recovered data is not trusted immediately.

The system recalculates its cryptographic state and verifies it against the blockchain anchor before writing the recovered DID document back to the database.

```text
Corrupted / Missing DID
          │
          ▼
   Recovery Mechanism
          │
          ▼
 Reconstructed Document
          │
          ▼
 Hash / Merkle Verification
          │
          ▼
   Blockchain Comparison
          │
      ┌───┴───┐
    Valid    Invalid
      │         │
      ▼         ▼
  Restore     Reject
```

---

## System Architecture

The project follows a hybrid on-chain/off-chain architecture.

```text
                         ┌───────────────────────┐
                         │ WeChat Mini Program   │
                         │       Frontend        │
                         └───────────┬───────────┘
                                     │
                                     │ HTTP API
                                     ▼
                         ┌───────────────────────┐
                         │     Flask Backend     │
                         │                       │
                         │  Application Services │
                         │  Domain Rules         │
                         │  Crypto Services      │
                         │  Recovery Services    │
                         └───────┬───────┬───────┘
                                 │       │
                    ┌────────────┘       └────────────┐
                    ▼                                 ▼
          ┌──────────────────┐              ┌──────────────────┐
          │     MongoDB      │              │    Blockchain    │
          │                  │              │    (Ganache)     │
          │ DID Documents    │              │                  │
          │ History          │              │ DID State        │
          │ Recovery Data    │              │ Document Hash    │
          │ Verify Records   │              │ Merkle Root      │
          └──────────────────┘              │ Version Hash     │
                                            └──────────────────┘
```

The main design principle is:

> **Store complete data off-chain, but store enough cryptographic evidence on-chain to verify whether the off-chain data can still be trusted.**

---

## Backend Architecture

The backend uses a layered structure to separate API handling, application logic, domain rules, infrastructure, and persistence.

```text
backend/
├── api/
│   └── routes/
│
├── application/
│   └── services/
│
├── domain/
│   ├── models/
│   └── rules/
│
├── infrastructure/
│   ├── blockchain/
│   ├── crypto/
│   ├── mongo/
│   └── storage/
│
├── persistence/
│   └── repositories/
│
├── scripts/
├── shared/
├── tests/
└── tools/
```

This structure helps isolate blockchain interaction, cryptographic operations, storage implementation, and business logic.

---

## Frontend

The user-facing client is implemented as a **WeChat Mini Program**.

Major pages include:

```text
frontend/pages/

├── index
├── login
├── didLatest
├── didUpdate
├── didVerify
├── didProof
├── didRecover
├── release
└── my
```

These pages provide interfaces for DID management and verification workflows.

---

## Smart Contract

The blockchain layer uses a Solidity smart contract to maintain trusted DID state summaries.

```text
contracts/
└── DIDState.sol
```

The contract is deployed to a local Ganache blockchain during development.

Deployment artifacts are stored in:

```text
deployments/
├── abi.json
├── address.json
└── deploy_metadata.json
```

The local development environment currently uses:

```text
Solidity: 0.8.20
Chain ID: 1337
Blockchain: Ganache
```

---

## Experimental Dashboard

A Streamlit-based experimental and visualization module is included in the project.

```text
streamlit_app/
├── components/
├── pages/
├── services/
└── utils/
```

The dashboard can be used to analyze system operations such as:

* DID registration;
* DID updates;
* integrity verification;
* DID recovery;
* operation latency;
* success rate;
* blockchain gas consumption;
* recovery storage overhead;
* recovery method comparison;
* failure analysis.

This layer is primarily used for evaluating the performance and security mechanisms of the system.

---

## Security Model

The project assumes that the off-chain storage environment may be untrusted.

Possible failures include:

| Threat                         | Protection Mechanism                 |
| ------------------------------ | ------------------------------------ |
| DID document tampering         | Document hash verification           |
| Attribute modification         | Merkle root verification             |
| Historical version rollback    | Version-state verification           |
| DID document deletion          | Recovery mechanisms                  |
| Corrupted recovery data        | Post-recovery integrity verification |
| Untrusted database state       | Blockchain state anchoring           |
| Excessive attribute disclosure | Attribute-level Merkle Proof         |

The blockchain is therefore used as a **trust anchor**, rather than as the primary storage layer.

---

## Technology Stack

| Layer                  | Technology                                |
| ---------------------- | ----------------------------------------- |
| Frontend               | WeChat Mini Program                       |
| Backend                | Python / Flask                            |
| Database               | MongoDB                                   |
| Blockchain             | Ethereum-compatible local blockchain      |
| Development Chain      | Ganache                                   |
| Smart Contract         | Solidity                                  |
| Blockchain Interaction | Web3                                      |
| Cryptography           | Hashing / Merkle Tree / Digital Signature |
| Data Recovery          | Multi-replica + XOR Erasure Coding        |
| Visualization          | Streamlit                                 |
| Containerization       | Docker / Dev Container                    |

---

## Project Structure

```text
did-project/
│
├── backend/              # Flask backend and core DID logic
├── contracts/            # Solidity smart contracts
├── deploy/               # Contract deployment utilities
├── deployments/          # ABI and local deployment metadata
├── docs/                 # Project documentation
├── frontend/             # WeChat Mini Program
├── streamlit_app/        # Experimental dashboard
├── key/                  # Local test-key instructions
├── .devcontainer/        # Development container configuration
├── .env.example          # Environment configuration template
└── README.md
```

---

## DID Workflow

A typical DID operation follows the workflow below:

```text
1. User submits DID operation
             │
             ▼
2. Flask backend validates request
             │
             ▼
3. Cryptographic state is generated
             │
       ┌─────┴─────┐
       ▼           ▼
4. MongoDB      5. Blockchain
Full Document      State Anchor
       │           │
       └─────┬─────┘
             ▼
6. Verification / consistency checking
             │
             ▼
7. Result returned to client
```

For verification operations, the backend independently reconstructs the expected cryptographic state from off-chain data and compares it with the blockchain record.

---

## Local Development

### Prerequisites

Recommended development dependencies include:

* Python
* MongoDB
* Node.js
* Ganache
* WeChat Developer Tools
* Docker / Docker Compose

### Environment Configuration

Create a local `.env` file based on `.env.example`:

```bash
cp .env.example .env
```

Example development configuration:

```env
FLASK_APP=app.py
FLASK_ENV=development

MONGO_URI=mongodb://mongo:27017/did_system
WEB3_PROVIDER=http://ganache:8545
CHAIN_ID=1337
CONTRACT_SOURCE_PATH=/contracts/DIDState.sol
```

> `.env` should not be committed to Git.

### Local Blockchain

Start the local Ganache blockchain before deploying the DID smart contract.

After deployment, contract information is generated under:

```text
deployments/
```

The backend uses the generated ABI and contract address to communicate with the blockchain.

---

## Testing

The project contains backend tests under:

```text
backend/tests/
```

The test environment is designed to validate the major DID workflows and security mechanisms.

Important scenarios include:

```text
DID Registration
      ↓
DID Update
      ↓
Integrity Verification
      ↓
Tampering Detection
      ↓
Rollback Detection
      ↓
Recovery
      ↓
Recovery Verification
```

---

## Research Motivation

Most blockchain identity discussions focus on how blockchain can establish decentralized trust.

This project investigates a more specific question:

> **Can decentralized identity remain trustworthy when its off-chain storage environment is not trustworthy?**

Instead of assuming that MongoDB or another external storage service always returns correct data, the system treats off-chain data as something that must be independently verified.

Blockchain provides an immutable reference state, while cryptographic structures connect that trusted state with the much larger DID document stored outside the chain.

The resulting architecture attempts to balance:

* blockchain storage cost;
* data integrity;
* recoverability;
* privacy;
* verification efficiency.

---

## Future Improvements

Several directions could extend the current prototype:

* support W3C DID methods and DID Core more completely;
* integrate Verifiable Credentials;
* introduce decentralized storage such as IPFS;
* deploy contracts to an Ethereum test network;
* improve key-management mechanisms;
* introduce wallet-based authentication;
* implement more advanced erasure coding;
* extend selective disclosure with zero-knowledge proofs;
* benchmark the system under larger workloads;
* provide a browser-based management interface.

---

## Academic Background

This repository contains the engineering implementation associated with my undergraduate research on:

**Blockchain-Based Decentralized Identity Authentication in Untrusted Storage Environments**

The research focuses on using blockchain state anchoring and cryptographic verification to improve the integrity, consistency, and recoverability of decentralized identity data stored outside the blockchain.

The repository is intended to demonstrate both the research prototype and its engineering implementation.

---

## Author

**Zetong Yin**

GitHub: `@goodbro123`

Research interests:

`Blockchain` · `Web3` · `Decentralized Identity` · `Cybersecurity` · `Backend Engineering`

---

## License

This project is currently published for academic and portfolio demonstration purposes.

No open-source license has been granted at this time.
