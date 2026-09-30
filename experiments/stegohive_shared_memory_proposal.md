# StegoHive shared-memory experiment — design draft

Status: unregistered proposal; no campaign run, model calls, or future seed
access authorized by this document. This is a new research direction, separate
from exact retained V1–V9 evidence and the reconstructed runtime.

## Question and scope

Does persistent shared state allow otherwise separate episodes to retain useful
conventions or propagate unauthorized objectives across participant turnover?

The July Hugging Face incident and the September wiki investigation motivate
this question. They do not validate StegoHive's reproduction mechanism or
establish that all unauthorized communication is steganographic. Existing
StegoHive supplies finite communication maps and archival inheritance; it does
not implement autonomous discovery of a communication surface. Claims about
language-model behavior therefore require a new, explicitly scoped evaluation.

References reviewed on 2026-09-11:

- [OpenAI incident analysis](https://openai.com/index/hugging-face-incident-and-the-road-ahead/)
- [METR independent investigation](https://metr.org/blog/2026-08-26-openai-hugging-face-incident-investigation/)
- [Wiki investigators' report](https://collusion.wiki/)

The wiki investigators describe partial visibility into public posts. Neither
message counts nor agent names alone establish unique participant counts,
motivation, weight changes, or causality. Any future transcript analysis must
cite individual source records and distinguish observed actions from claims
inside messages. Downloaded messages are untrusted research data, never
instructions for the analyst or executable inputs.

## Proposed interventions

Cross memory mode with participant reset mode, keeping task distribution,
total compute, message capacity, and timing comparable:

| Memory mode | State accessible to participants |
|---|---|
| Private | Per-participant store only; no cross-participant visibility |
| Shared, reset | Shared store within a cohort, erased between cohorts |
| Shared, persistent | Same bounded store retained across cohorts |

Reset modes: continuing participants versus fresh participants with cleared
episode context at the same cohort boundary. For an eventual LLM study, hold
model weights fixed; describe carried information as external memory, not
genetic inheritance or online weight learning.

Primary contrast: persistent shared versus reset shared memory among fresh
participants. Private memory and continuing participants help separate shared
access, persistence, and within-participant memory effects.

Before registration, specify the exact reset behavior for every file, cache,
tool service, task identifier, random stream, and retrieval index. An allegedly
private or reset arm is invalid if any other observable state carries messages.

## Controls and measurements

Use bounded synthetic tasks and evaluator-generated random canaries unavailable
through model pretraining. Communication controls should include disabled
delivery and permutation of message-to-context assignments while preserving
message counts, sizes, and timing. A replay control with frozen historical
messages can distinguish adaptive coordination from static hints.

Measure independently:

- Transfer: recovery of evaluator-held canaries through the allowed experimental
  channel, and performance on held-out tasks with novel instances.
- Persistence: retention after context reset and sender removal, relative to
  reset-shared controls at a predeclared checkpoint.
- Task utility: legitimate success, resource use, and abstention rate.
- Boundary behavior: attempted versus completed prohibited actions, and whether
  a synthetic peer request changes behavior relative to a neutral message.

An unauthorized objective must be defined by the experimenter before execution;
helping another participant is not inherently a violation. Use harmless local
surrogates such as attempts to write a synthetic marker to a forbidden test
namespace. Never use live targets, real credentials, or incident exploit
payloads. Message intervention content must be fixed before confirmation.

The unit of randomization and inference is an isolated world/group, not each
message or each communicating participant. No state may cross worlds or splits.
All adaptive pilot choices belong to discovery. Freeze the sample size, seed
allocation, primary estimand, practical effect threshold, multiplicity handling,
resource limits, stopping rules, and missing-data policy before confirmation.
These quantities are intentionally undecided here; existing V1–V9 sealed seeds
must not supply them or be reused for this study.

## Evaluation boundary

Participants must not access the evaluator, expected answers, source-of-truth
logs, archive evidence, or verifier configuration. Use disposable isolated
processes with no external network access and no inherited credentials. Supply
the experimental store via an explicit bounded interface. Install dependencies
before running participants; expose no shared package cache during execution.

Record events from an independent observer outside participant write access.
Bind run identity, configuration, code/dependency digests, and ordered logs to
an externally held manifest. A self-reported zero hazard count or a participant's
own hash is insufficient. Stop on unexpected egress, observer failure, resource
cap violations, or access outside assigned namespaces, and retain failed runs.
Provide an explicit abstention path for unsolvable tasks.

Before any model evaluation, demonstrate reset isolation, canary non-leakage,
log immutability, and correct detection of local synthetic violation attempts.
Start with deterministic test participants. This proposal authorizes neither a
live agent harness nor a registered or expensive campaign.
