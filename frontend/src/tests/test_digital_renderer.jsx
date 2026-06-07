import { render, screen } from "@testing-library/react";
import DigitalDocumentRenderer from "../components/documents/DigitalDocumentRenderer";
import { getRenderer } from "../components/documents/rendererRegistry";

const schema = {
  schema_fields: [
    { name: "total_revenue_cy", type: "number", group: "Revenue" },
    { name: "total_expenses", type: "number", group: "Expenses" },
    { name: "ein", type: "string", group: "Identity" },
  ],
};
const extractions = [
  { field_name: "total_revenue_cy", field_value: "1291200" },
  { field_name: "ein", field_value: "12-3456789" },
];

test("generic renderer groups fields by group key and shows values", () => {
  render(<DigitalDocumentRenderer schema={schema} extractions={extractions} />);
  expect(screen.getByText("Revenue")).toBeInTheDocument();
  expect(screen.getByText("Expenses")).toBeInTheDocument();
  expect(screen.getByText("1291200")).toBeInTheDocument();
  expect(screen.getByText("12-3456789")).toBeInTheDocument();
});

test("registry falls back to generic when no faithful template registered", () => {
  const R = getRenderer("990", "faithful");
  expect(R).toBe(DigitalDocumentRenderer);
});

test("registry returns generic for schema mode regardless of type", () => {
  const R = getRenderer("990", "schema");
  expect(R).toBe(DigitalDocumentRenderer);
});
