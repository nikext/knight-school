import { MODEL_COLOR, pct } from "../lib";
import type { Dataset } from "../types";

const REPO = "https://github.com/nikext/knight-school";

export default function About({ data }: { data: Dataset }) {
  return (
    <main className="page prose-page">
      <header className="page-head">
        <h1>About this browser</h1>
        <p className="lede">
          Knight School asks whether a cheap, teacher-free “chess primer”, meaning supervised fine-tuning on board reading, rules and
          Stockfish-annotated positions built from CC0 Lichess data, raises what reinforcement learning (GRPO) can reach with a small open
          LLM. This page shows every answer behind the headline numbers.
        </p>
      </header>

      <section className="card prose">
        <h2>The models</h2>
        <ul className="model-list">
          {data.models.map((m) => (
            <li key={m.key}>
              <span className="swatch" style={{ background: MODEL_COLOR[m.key] }} />
              <div>
                <strong>{m.label}</strong> <span className="muted">· {pct(m.solve.value)} solved</span>
                <div className="muted small">
                  {m.blurb}. Eval run <code>{m.run}</code>.
                </div>
              </div>
            </li>
          ))}
        </ul>
        <p>
          Both RL rows use the same sparse reward (1 for the right move, else 0), the same GRPO config and 200 steps. They differ only in
          the model they start from. All four LLM rows are Qwen3.5-2B.
        </p>

        <h2>How a puzzle is graded</h2>
        <p>
          The model sees the position as a FEN, the side to move, and the list of legal moves in SAN. It answers in{" "}
          <code>&lt;answer&gt;…&lt;/answer&gt;</code> tags. At each of the solver's moves it is shown the position reached by the correct line
          so far, so one mistake doesn't spoil the later moves. A puzzle is solved when every solver move is right. As on Lichess, any mate
          counts on the final move. Decoding is greedy.
        </p>
        <p>
          <strong>There is no reasoning text to show.</strong> The model runs in non-thinking mode, and every model here answers directly,
          in about ten tokens. Whatever skill it has is in the move it picks.
        </p>

        <h2>What it is not</h2>
        <p>
          A puzzle solve rate, not a playing strength. Puzzles come with a forcing tactic and the legal moves come for free. Without the
          list, the best model solves 1.9%. Nothing here plays games, and none of it is meant to help anyone during one.
        </p>

        <h2>Data and licences</h2>
        <p>
          Puzzles: the <a href="https://database.lichess.org/#puzzles">Lichess puzzle database</a> (CC0), 2,000 held out by game and
          stratified by rating. Board: <a href="https://github.com/Clariity/react-chessboard">react-chessboard</a> (MIT) with{" "}
          <a href="https://github.com/jhlywa/chess.js">chess.js</a> (BSD-2). Code, configs, every eval file and the cost ledger are in{" "}
          <a href={REPO}>the repository</a>.
        </p>
      </section>
    </main>
  );
}
