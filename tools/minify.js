#!/usr/bin/env node

const {minify: minifyJs} = require('terser')
const {minify: minifyHtml} = require('html-minifier-terser')
const CleanCSS = require('clean-css');
const parseArgs = require('minimist')
const {promises: fs} = require('fs')

const argv = process.argv.slice(2)
if (!argv.length) {
    console.log(`usage: ${process.argv[1]} --type js|css|html filename`)
    process.exit(1)
}

async function read() {
    const chunks = []
    for await (const chunk of process.stdin)
        chunks.push(chunk)
    return Buffer.concat(chunks).toString('utf-8')
}

const args = parseArgs(argv, {
    string: ['type'],
})

;(async () => {
    if (!['js', 'css', 'html'].includes(args.type))
        throw new Error('invalid type')

    const content = await read()

    switch (args.type) {
        case 'html':
            console.log(await minifyHtml(content, {
                collapseBooleanAttributes: true,
                collapseInlineTagWhitespace: true,
                collapseWhitespace: true,
                conservativeCollapse: true,
                html5: true,
                includeAutoGeneratedTags: true,
                keepClosingSlash: false,
                minifyCSS: true,
                minifyJS: true,
                minifyURLs: false,
                preserveLineBreaks: true,
                removeComments: true,
                removeAttributeQuotes: false,
                sortAttributes: false,
                sortClassName: false,
                useShortDoctype: true,
            }))
            break

        case 'css':
            console.log(new CleanCSS({level:2}).minify(content).styles)
            break

        case 'js':
            console.log((await minifyJs(content, {
                ecma: 5
            })).code)
            break
    }
})()
