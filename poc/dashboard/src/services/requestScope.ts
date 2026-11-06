// In-memory selection only; the backend independently verifies every requested department.
let selectedDepartment: string | null = null;
export const setRequestDepartment = (id: string | null) => { selectedDepartment = id; };
export const getRequestDepartment = () => selectedDepartment;
