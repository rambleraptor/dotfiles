# SetDjangoSyntax

a quick and dirty little sublime text 2 plugin that attempts to set the syntax of the open buffer to "python django" when appropriate.

it is dependent on having already installed the [djaneiro](https://github.com/squ1b3r/djaneiro) package.

the way that SetDjangoSyntax works is probably pretty dumb, but in practice it seems to work fairly well on my box. please fork the repo and improve it if you can. at present, all it does is search the text of an open buffer whose filename ends in '.py' for a string that equals "from django". if it finds that string it sets the syntax to "python django".

install SetDjangoSyntax via [package control](http://wbond.net/sublime_packages/package_control) or you can download [here](https://bitbucket.org/pjv/setdjangosyntax) and install manually by copying to your sublime text 2 package directory.

### License

This is free and unencumbered software released into the public domain.

Anyone is free to copy, modify, publish, use, compile, sell, or
distribute this software, either in source code form or as a compiled
binary, for any purpose, commercial or non-commercial, and by any
means.

In jurisdictions that recognize copyright laws, the author or authors
of this software dedicate any and all copyright interest in the
software to the public domain. We make this dedication for the benefit
of the public at large and to the detriment of our heirs and
successors. We intend this dedication to be an overt act of
relinquishment in perpetuity of all present and future rights to this
software under copyright law.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR
OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
OTHER DEALINGS IN THE SOFTWARE.

For more information, please refer to <http://unlicense.org/>