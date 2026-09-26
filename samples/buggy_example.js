// Sample with several real bugs for the demo reviewer.
const fs = require('fs');

function loadConfig(path) {
    let data = fs.readFileSync(path);
    if (data == null) {
        return {};
    }
    let parsed = JSON.parse(data);
    return parsed;
}

function greet(name) {
    // TODO: internationalise this message
    console.log("Hello, " + name);
    return formatGreeting(name);
}
