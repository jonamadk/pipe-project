export default function Composer({ value, onChange, onSubmit, disabled }) {
  return (
    <div className="composer">
      <form
        id="composer-form"
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit();
        }}
      >
        <input
          id="q-input"
          type="text"
          placeholder="e.g. What temperature should my water heater be set to?"
          autoComplete="off"
          value={value}
          onChange={(e) => onChange(e.target.value)}
        />
        <button type="submit" id="send-btn" disabled={disabled}>
          Ask
        </button>
      </form>
      <div className="disclaimer">
        Demo only — not a substitute for a licensed plumber, health inspector, or your building's
        water management program.
      </div>
    </div>
  );
}
