/** @type {import('tailwindcss').Config} */
module.exports = {
    content: ["./app/templates/**/*.html", "./app/static/**/*.js"],
    theme: {
        extend: {
            colors: {
                dracula: {
                    bg: '#282a36',
                    selection: '#44475a',
                    fg: '#f8f8f2',
                    comment: '#6272a4',
                    cyan: '#8be9fd',
                    green: '#50fa7b',
                    orange: '#ffb86c',
                    pink: '#ff79c6',
                    purple: '#bd93f9',
                    red: '#ff5555',
                    yellow: '#f1fa8c',
                },
            },
            fontFamily: {
                outfit: ['Outfit', 'sans-serif'],
            },
        },
    },
    plugins: [],
};
