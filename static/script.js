async function submitQuery() {
    console.log("submitQuery called");
    const queryInput = document.getElementById("queryInput").value;
    const sqlOutput = document.getElementById("sqlOutput");
    const resultsOutput = document.getElementById("resultsOutput");
    const errorOutput = document.getElementById("errorOutput");
    const loading = document.getElementById("loading");

    if (!queryInput) {
        console.warn("Empty query input");
        errorOutput.textContent = "Please enter a query!";
        errorOutput.classList.remove("hidden");
        return;
    }

    // Clear previous outputs
    errorOutput.classList.add("hidden");
    errorOutput.textContent = "";
    sqlOutput.textContent = "";
    resultsOutput.innerHTML = "";
    loading.classList.remove("hidden");

    console.log("Sending query:", queryInput);
    try {
        const response = await fetch("/query", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ query: queryInput })
        });

        console.log("Response status:", response.status);
        if (!response.ok) {
            const errorText = await response.text();
            console.error("API error:", errorText);
            throw new Error(`HTTP error! Status: ${response.status}, Message: ${errorText}`);
        }

        const data = await response.json();
        console.log("API response:", data);

        sqlOutput.textContent = `Generated SQL:\n${data.sql || "No SQL returned"}`;
        resultsOutput.innerHTML = "";

        if (!data.results || data.results.length === 0) {
            console.warn("No results in response");
            resultsOutput.textContent = "No results found.";
            return;
        }

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
                td.textContent = value || "";
                row.appendChild(td);
            });
            tbody.appendChild(row);
        });

        table.appendChild(thead);
        table.appendChild(tbody);
        resultsOutput.appendChild(table);
    } catch (error) {
        console.error("Fetch error:", error.message);
        errorOutput.textContent = `Error: ${error.message}`;
        errorOutput.classList.remove("hidden");
    } finally {
        loading.classList.add("hidden");
    }
}
