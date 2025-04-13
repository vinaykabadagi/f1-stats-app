// Debounce function to prevent rapid-fire API calls
const debounce = (func, wait) => {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
};

// Show loading state
function setLoading(isLoading) {
    const button = document.querySelector('#submit-button');
    const loader = document.querySelector('#loader');
    if (isLoading) {
        button.disabled = true;
        loader.style.display = 'block';
    } else {
        button.disabled = false;
        loader.style.display = 'none';
    }
}

// Format the results into a table
function formatResults(results) {
    if (!results || results.length === 0) {
        return '<p>No results found</p>';
    }

    const columns = Object.keys(results[0]);
    let table = '<table class="results-table"><thead><tr>';
    
    // Add headers
    columns.forEach(column => {
        table += `<th>${column}</th>`;
    });
    table += '</tr></thead><tbody>';
    
    // Add data rows
    results.forEach(row => {
        table += '<tr>';
        columns.forEach(column => {
            table += `<td>${row[column] ?? ''}</td>`;
        });
        table += '</tr>';
    });
    
    table += '</tbody></table>';
    return table;
}

// Handle API errors
function handleError(error) {
    const resultsDiv = document.querySelector('#results');
    resultsDiv.innerHTML = `
        <div class="error-message">
            <p>Error: ${error.message || 'Something went wrong'}</p>
            <p>Please try rephrasing your query or try again later.</p>
        </div>
    `;
}

// Submit query with debouncing
const submitQuery = debounce(async () => {
    const query = document.querySelector('#query').value;
    const resultsDiv = document.querySelector('#results');
    const sqlDiv = document.querySelector('#sql-query');
    
    if (!query.trim()) {
        resultsDiv.innerHTML = '<p>Please enter a query</p>';
        return;
    }

    setLoading(true);
    try {
        const response = await fetch('/query', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ query }),
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to fetch results');
        }

        const data = await response.json();
        sqlDiv.innerHTML = `<pre><code>${data.sql}</code></pre>`;
        resultsDiv.innerHTML = formatResults(data.results);
    } catch (error) {
        handleError(error);
    } finally {
        setLoading(false);
    }
}, 500);

// Initialize event listeners
document.addEventListener('DOMContentLoaded', () => {
    const input = document.querySelector('#query');
    const form = document.querySelector('#query-form');
    
    form.addEventListener('submit', (e) => {
        e.preventDefault();
        submitQuery();
    });

    // Optional: Submit on input after debounce
    input.addEventListener('input', submitQuery);
});
