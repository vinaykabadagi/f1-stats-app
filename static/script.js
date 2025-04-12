// Error handling utility
function showError(message) {
    const errorOutput = document.getElementById("errorOutput");
    errorOutput.textContent = message;
    errorOutput.classList.remove("hidden");
}

// Success message utility
function showSuccess(message) {
    const successOutput = document.getElementById("successOutput");
    successOutput.textContent = message;
    successOutput.classList.remove("hidden");
    setTimeout(() => {
        successOutput.classList.add("hidden");
    }, 3000);
}

// Create chart canvas
function createChartSection() {
    const chartSection = document.createElement("div");
    chartSection.id = "chartSection";
    chartSection.classList.add("chart-section");
    
    const canvas = document.createElement("canvas");
    canvas.id = "resultsChart";
    chartSection.appendChild(canvas);
    
    return chartSection;
}

// Attempt to visualize data
function visualizeData(results) {
    if (!results || results.length === 0) return;

    const chartSection = document.getElementById("chartSection") || createChartSection();
    document.getElementById("resultsOutput").appendChild(chartSection);

    // Get numeric columns
    const sampleRow = results[0];
    const numericColumns = Object.entries(sampleRow)
        .filter(([key, value]) => typeof value === 'number')
        .map(([key]) => key);

    if (numericColumns.length === 0) return; // No numeric data to visualize

    const canvas = document.getElementById("resultsChart");
    const ctx = canvas.getContext("2d");

    // Clear existing chart
    if (window.currentChart) {
        window.currentChart.destroy();
    }

    // Prepare chart data
    const labels = results.map((row, index) => index + 1);
    const datasets = numericColumns.map(column => ({
        label: column,
        data: results.map(row => row[column]),
        borderColor: `hsl(${Math.random() * 360}, 70%, 50%)`,
        tension: 0.1
    }));

    // Create new chart
    window.currentChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: datasets
        },
        options: {
            responsive: true,
            plugins: {
                title: {
                    display: true,
                    text: 'Data Visualization'
                }
            }
        }
    });
}

// Export results to CSV
function exportToCSV(results) {
    if (!results || results.length === 0) return;

    const headers = Object.keys(results[0]);
    const csvContent = [
        headers.join(','),
        ...results.map(row => headers.map(header => {
            const value = row[header];
            return typeof value === 'string' ? `"${value}"` : value;
        }).join(','))
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.setAttribute('href', url);
    a.setAttribute('download', 'f1_stats_results.csv');
    a.click();
    window.URL.revokeObjectURL(url);
}

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        submitQuery();
    } else if (e.key === '/' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        document.getElementById('queryInput').focus();
    }
});

// Global state for pagination
let currentPage = 1;
let totalPages = 1;

function updatePaginationControls() {
    const paginationDiv = document.getElementById('pagination');
    if (!paginationDiv) return;

    paginationDiv.innerHTML = `
        <button onclick="changePage(-1)" ${currentPage <= 1 ? 'disabled' : ''}>Previous</button>
        <span>Page ${currentPage} of ${totalPages}</span>
        <button onclick="changePage(1)" ${currentPage >= totalPages ? 'disabled' : ''}>Next</button>
    `;
}

function changePage(delta) {
    const newPage = currentPage + delta;
    if (newPage >= 1 && newPage <= totalPages) {
        currentPage = newPage;
        submitQuery(true);
    }
}

async function submitQuery(isPageChange = false) {
    console.log("submitQuery called");
    const queryInput = document.getElementById("queryInput");
    const sqlOutput = document.getElementById("sqlOutput");
    const resultsOutput = document.getElementById("resultsOutput");
    const errorOutput = document.getElementById("errorOutput");
    const loading = document.getElementById("loading");
    const exportButton = document.getElementById("exportButton");

    if (!queryInput.value.trim()) {
        showError("Please enter a query!");
        return;
    }

    // Don't clear the query input on page changes
    if (!isPageChange) {
        currentPage = 1;
    }

    // Clear previous outputs
    errorOutput.classList.add("hidden");
    sqlOutput.textContent = "";
    resultsOutput.innerHTML = "";
    loading.classList.remove("hidden");
    if (exportButton) exportButton.classList.add("hidden");

    try {
        const response = await fetch("/query", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ 
                query: queryInput.value,
                page: currentPage
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.message || "An error occurred while fetching data");
        }

        // Display SQL
        sqlOutput.textContent = `Generated SQL:\n${data.sql || "No SQL returned"}`;

        // Handle no results
        if (!data.results || data.results.length === 0) {
            resultsOutput.textContent = "No results found.";
            return;
        }

        // Create results table
        const table = document.createElement("table");
        const thead = document.createElement("thead");
        const tbody = document.createElement("tbody");

        // Create header
        const headerRow = document.createElement("tr");
        Object.keys(data.results[0]).forEach(key => {
            const th = document.createElement("th");
            th.textContent = key;
            headerRow.appendChild(th);
        });
        thead.appendChild(headerRow);

        // Create rows
        data.results.forEach(result => {
            const row = document.createElement("tr");
            Object.values(result).forEach(value => {
                const td = document.createElement("td");
                td.textContent = value !== null ? value : "";
                row.appendChild(td);
            });
            tbody.appendChild(row);
        });

        table.appendChild(thead);
        table.appendChild(tbody);
        resultsOutput.appendChild(table);

        // Add pagination controls
        if (data.total_pages > 1) {
            totalPages = data.total_pages;
            const paginationDiv = document.createElement("div");
            paginationDiv.id = "pagination";
            paginationDiv.classList.add("pagination");
            resultsOutput.appendChild(paginationDiv);
            updatePaginationControls();
        }

        // Add export button
        const exportButton = document.createElement("button");
        exportButton.id = "exportButton";
        exportButton.textContent = "Export to CSV";
        exportButton.onclick = () => exportToCSV(data.results);
        exportButton.classList.add("export-button");
        resultsOutput.appendChild(exportButton);

        // Attempt to visualize data
        visualizeData(data.results);

        showSuccess(`Found ${data.total_count || data.results.length} results`);

    } catch (error) {
        console.error("Error:", error);
        showError(error.message || "An error occurred while processing your request");
    } finally {
        loading.classList.add("hidden");
    }
}