-- SQLite Schema for Agentic OPS Assistant POC

-- Turn on foreign key support
PRAGMA foreign_keys = ON;

-- -----------------------------------------------------
-- Table `employees`
-- Stores details about employees from the Master File.
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS employees (
  employee_id TEXT PRIMARY KEY,
  employee_name TEXT NOT NULL,
  status TEXT NOT NULL, -- e.g., 'Active', 'Inactive'
  standard_hours_per_week REAL,
  employee_category TEXT,
  employee_competency TEXT,
  employee_location TEXT,
  employee_billing_rank TEXT,
  department TEXT,
  region TEXT
);

-- Indexes for efficient filtering and joining with targets
CREATE INDEX IF NOT EXISTS idx_employees_status ON employees(status);
CREATE INDEX IF NOT EXISTS idx_employees_category ON employees(employee_category);
CREATE INDEX IF NOT EXISTS idx_employees_competency ON employees(employee_competency);
CREATE INDEX IF NOT EXISTS idx_employees_location ON employees(employee_location);
CREATE INDEX IF NOT EXISTS idx_employees_billing_rank ON employees(employee_billing_rank);

-- -----------------------------------------------------
-- Table `projects`
-- Stores details about projects from the MLP.
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS projects (
  project_id TEXT PRIMARY KEY,
  project_name TEXT NOT NULL,
  project_status TEXT,
  project_start_date DATE,
  project_end_date DATE,
  total_budgeted_hours REAL,
  required_primary_skill TEXT,
  target_resource_count REAL -- FTE
);

-- Indexes for filtering
CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(project_status);
CREATE INDEX IF NOT EXISTS idx_projects_start_date ON projects(project_start_date);
CREATE INDEX IF NOT EXISTS idx_projects_end_date ON projects(project_end_date);


-- -----------------------------------------------------
-- Table `charged_hours`
-- Stores individual time entries, linking employees and projects.
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS charged_hours (
  charge_id INTEGER PRIMARY KEY AUTOINCREMENT,
  employee_id TEXT NOT NULL,
  project_id TEXT NOT NULL,
  charge_date DATE NOT NULL,
  charged_hours REAL NOT NULL,
  FOREIGN KEY (employee_id) REFERENCES employees(employee_id) ON DELETE RESTRICT ON UPDATE CASCADE,
  FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE RESTRICT ON UPDATE CASCADE
);

-- Indexes for aggregation and filtering
CREATE INDEX IF NOT EXISTS idx_charged_hours_employee_id ON charged_hours(employee_id);
CREATE INDEX IF NOT EXISTS idx_charged_hours_project_id ON charged_hours(project_id);
CREATE INDEX IF NOT EXISTS idx_charged_hours_charge_date ON charged_hours(charge_date);

-- -----------------------------------------------------
-- Table `targets`
-- Stores monthly performance targets based on employee dimensions.
-- Uses a composite primary key.
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS targets (
  target_year INTEGER NOT NULL,
  target_month INTEGER NOT NULL,
  employee_category TEXT NOT NULL,
  employee_competency TEXT NOT NULL,
  employee_location TEXT NOT NULL,
  employee_billing_rank TEXT NOT NULL,
  target_utilization_percentage REAL,
  target_charged_hours_per_fte REAL,
  target_headcount_fte REAL,
  PRIMARY KEY (target_year, target_month, employee_category, employee_competency, employee_location, employee_billing_rank)
);

-- Individual indexes on dimensions might be useful depending on query patterns,
-- but the composite PK often covers many filtering scenarios. Let's add them for flexibility.
CREATE INDEX IF NOT EXISTS idx_targets_year_month ON targets(target_year, target_month);
CREATE INDEX IF NOT EXISTS idx_targets_category ON targets(employee_category);
CREATE INDEX IF NOT EXISTS idx_targets_competency ON targets(employee_competency);
CREATE INDEX IF NOT EXISTS idx_targets_location ON targets(employee_location);
CREATE INDEX IF NOT EXISTS idx_targets_billing_rank ON targets(employee_billing_rank); 