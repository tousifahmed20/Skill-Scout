# The folder method used here (for humans)

Source: Jake Van Clief and David McDermott, *Interpretable Context Methodology: Folder Structure as Agentic Architecture* (arXiv 2603.16021), and his example repo `RinDig/Content-Agent-Routing-Promptbase`. Written in simplified technical English.

## The main idea
The folder structure is the agent architecture. Folders replace orchestration code. Markdown files hold the instructions. One agent reads only the files for its current step.

## The layers
| Layer | Here | Question it answers |
|---|---|---|
| 0 | `CLAUDE.md` | Where am I? |
| 1 | `CONTEXT.md` | Where do I go? |
| 2 | `stages/NN_name/CONTEXT.md` | What do I do? |
| 3 | `stages/NN_name/references/` | Which rules apply? |
| 4 | code and data the stage writes | What do I work on? |

## The rules
- One stage does one job.
- Numbers show the order.
- Each fact has one home. Other files point to it.
- Dependencies go one way. A later stage reads an earlier stage. An earlier stage does not read a later stage.
- Routing files contain only routes.
- Machine files say "what". Human files say "why".

## What this repo adds: routed reads
Most features need only their own stage folder. A few need facts from earlier stages.
- The routing table marks each stage `single` or `multi`.
- A `multi` stage lists the exact files and sections it needs in its Inputs table. It names a section, not a whole folder.
- The agent reads nothing else. If it needs a fact that is not listed, it stops, adds the route, and runs the checker.
- `tools/check_routes.py` makes sure every route exists, points backward only, and matches the routing table.

The shipped skill uses the same idea. `SKILL.md` lists each step with the files it loads and when. A cached query loads only the router and three short step files.

## Limits the authors state
- The evidence comes from reports by a small community of users.
- The tests used one model family (Claude).
- There is no controlled comparison with one large prompt.
- The method is not for real-time multi-agent systems or multi-user servers. For this reason the Hive server (stage 10) is ordinary code; only the build workspace and the skill use the folder method.
