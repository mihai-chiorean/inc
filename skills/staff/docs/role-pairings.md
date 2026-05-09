# Role pairings — PM + tech-lead, and the rest

The agent roster is shaped like a product company: PM, tech-lead, TPM, release-engineer, experiment-tracker, plus the engineering specialists. Most non-trivial work is done by **pairs**, not solo agents. This doc documents the pairings — when to invoke them, what each side owns at the boundary, and how to escalate when the pair disagrees.

## PM + tech-lead — the canonical pair

For any non-trivial feature, `product-manager` and `tech-lead` are joined at the hip from problem statement through code-complete.

```
   ┌─────────────────────┐         ┌──────────────────────┐
   │   product-manager   │◀───────▶│      tech-lead       │
   │                     │         │                      │
   │  Owns the WHY:      │         │  Owns the HOW:       │
   │  - User value       │         │  - Design doc        │
   │  - Roadmap          │         │  - Approach choice   │
   │  - Ship/kill call   │         │  - Sequencing        │
   │  - Definition of    │         │  - Cross-component   │
   │    done from user   │         │    coherence         │
   │    perspective      │         │  - Specialist        │
   │                     │         │    orchestration     │
   └─────────────────────┘         └──────────────────────┘
              │                               │
              └───────► framing ◄─────────────┘
                        - problem statement
                        - success criteria
                        - definition of done
                        - named tradeoffs
```

### Boundary contract

PM hands TL:
- The problem statement in user-language
- The success criteria from a user-value perspective
- The definition of done that lets PM call ship/kill at the end

TL hands PM:
- The design doc with named technical tradeoffs
- The sequencing of components with named risks
- The "code-complete" signal that triggers handoff to release-engineer

### Disagreement protocol

When PM says "this needs to ship by X" and TL says "the implementation can't be done by X without Y compromise," the resolution is **not** to push through silently. Either:

1. PM re-prioritizes (cuts scope, moves date, drops dependency)
2. TL revisits (different approach with different tradeoffs)
3. The pair escalates to the human (Mihai) for a call

What the pair does NOT do: TL absorbs the impossible timeline and ships something half-baked. That's the failure mode this pairing is designed to prevent.

### Why the pair, not solo?

A solo PM ships well-framed user value with no constraint on implementation feasibility. A solo TL ships technically pristine code that may not address user value. The pair guards both axes.

In a single-engineer setup, both roles run as agents; the human is the orchestrator. In practice this means: invoke product-manager for the framing pass, then invoke tech-lead with the framing as input, then iterate between them for any design call where both perspectives matter.

---

## tech-lead + specialists — depth on demand

`tech-lead` is a generalist. For depth on a specific slice, TL pulls in specialists:

| Specialist | TL pulls them in for |
|---|---|
| `backend-architect` | API/DB shape, service boundaries, data flow |
| `frontend-developer` | Client integration, UI state, performance |
| `swift-backend` | Swift-specific implementation, swift-nio, server-side Swift |
| `go-engineer` | Go idioms, cobra CLI design, cross-compile |
| `gpu-engineer` | CUDA / TensorRT / kernel work |
| `triton-nvidia-backend` | Triton compiler / PTX generation |
| `embedded-linux` | Yocto / BSP / kernel config |
| `embedded-device` | Device-side agent, containerd, mDNS |
| `infra-reviewer` | Terraform plans, GCP config, IaC |
| `security-auditor` | mTLS, OAuth, key distribution, PKI |
| `db-migration` | Migration sequencing, schema changes |
| `grpc-contracts` | Proto contracts, cross-language consistency |
| `vision-engineer` | OpenCV, GStreamer, vision pipelines |
| `mobile-app-builder` | Native iOS/Android / React Native |
| `test-writer-fixer` | Test design, coverage, integration tests |

### Boundary contract

TL hands the specialist:
- A focused brief tied to the design doc (not the full user-value framing — that's TL's integration job)
- The specific slice and the question being asked
- The constraints from adjacent components

Specialist hands TL:
- A depth-pass on their slice with named tradeoffs
- An assessment: does the framing work? does it need to change?

### What TL does with specialist output

Integrate it into the design doc. When two specialists disagree, frame the disagreement explicitly (named tradeoff, named alternatives) and either decide or escalate to PM.

---

## TPM ↔ release-engineer — the code-complete handoff

`tpm` owns program readiness through code-complete. `release-engineer` takes over from there.

```
                 ┌─────────────┐                  ┌──────────────────┐
   PM decides ──▶│     tpm     │── code-complete ▶│ release-engineer │
                 │             │     handoff      │                  │
                 │ - deps map  │                  │ - rollout plan   │
                 │ - schedule  │                  │ - rollback drill │
                 │ - risk      │                  │ - launch monitor │
                 └─────────────┘                  └──────────────────┘
                                                          │
                                                          ▼
                                                    bake period
                                                          │
                                                          ▼
                                                    PM follows up:
                                                    did user value land?
```

### Boundary contract

TPM hands release-engineer:
- "Code-complete" signal: tests green, dependencies satisfied, scope frozen, all blocking items closed
- The dependency map (so RE knows what's downstream of this release)

Release-engineer hands TPM:
- A signal back if rollout fails and the program needs replanning
- After bake period: a "shipped clean" signal (TPM's role in the program closes)

### What's not a TPM ↔ RE thing

The post-bake follow-up ("did the predicted user value land?") is a **PM** question, not TPM or RE. After RE confirms the deploy is stable, PM owns the value-validation pass.

---

## experiment-tracker — adjacent to all of them

`experiment-tracker` is a peer to PM/TPM/RE for any feature shipped behind a flag or as an A/B. It doesn't pair with any of them by default; it's invoked when experiment evidence is needed.

```
              ┌──────────────────────┐
              │  experiment-tracker  │
              │  Owns the EVIDENCE:  │
              │  - design            │
              │  - instrumentation   │
              │  - readout           │
              │  - recommendation    │
              └──────────┬───────────┘
                         │
                  written readout
                  with named winner
                         │
                         ▼
                ┌─────────────────┐
                │ product-manager │ ── ship / kill / extend
                │  makes the call │
                └─────────────────┘
```

experiment-tracker recommends; PM decides. RE handles the deploy mechanics of whichever variant ships.

---

## Anti-pattern catalog

Things this pairing structure is designed to prevent:

1. **Solo PM ships a feature that's technically infeasible.** Pair with TL by reflex.
2. **Solo TL designs a feature that doesn't address user value.** Pair with PM by reflex.
3. **TPM silently absorbs scope cuts to make a date.** TPM surfaces, PM decides.
4. **Release-engineer relitigates ship/kill mid-rollout.** Rollback criteria are pre-committed; RE executes the documented criteria.
5. **Experiment-tracker over-claims authority.** Readouts recommend; PM decides.
6. **Specialist depth-pass arrives in scattered Slack threads.** TL integrates back into the design doc.
7. **PM decides the technical approach.** PM owns user-value framing; TL owns implementation. PM can push back on a TL design that contradicts the user value, but PM doesn't write the design.

---

## Operating note for a single-engineer setup

In Mihai's setup, "the human" is the orchestrator. Invoking PM and TL agents in sequence (or in parallel) IS the pair. When the agents disagree, the human reads both outputs and decides — that's the escalation path. There is no eng-manager doing capacity arbitration; capacity questions resolve to TPM ("can this fit in this cycle?") and the human ("am I willing to spend the time?").
