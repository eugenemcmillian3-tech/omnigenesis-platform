from pathlib import Path
from html.parser import HTMLParser
import json
import unittest
try:
 import quickjs
except ImportError:
 quickjs = None
class Elements(HTMLParser):
 def __init__(self):super().__init__();self.items={}
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if 'id' in a:self.items[a['id']]={'value':a.get('value',''),'textContent':''}
h=(Path(__file__).resolve().parents[1] / 'omnigenesis_dashboard.html').read_text(); parser=Elements();parser.feed(h)

def dashboard_context():
    c=quickjs.Context();c.eval('const elementSeeds='+json.dumps(parser.items))
    c.eval(r'''
    const events = {};
    const noop = () => {};
    const canvas = new Proxy({createLinearGradient:()=>({addColorStop:noop}),createRadialGradient:()=>({addColorStop:noop}),measureText:()=>({width:10})},{get:(o,k)=>k in o?o[k]:noop,set:(o,k,v)=>(o[k]=v,true)});
    function element(seed={}) {return Object.assign({value:'',textContent:'',innerHTML:'',children:[],handlers:{},options:[],selectedOptions:[{dataset:{}}],dataset:{},style:{},classList:{add:noop,remove:noop,toggle:noop,contains:()=>false},
    addEventListener(name,cb){this.handlers[name]=cb}, appendChild(x){this.children.push(x);return x}, prepend(...items){this.children.unshift(...items)},append(...items){this.children.push(...items)},replaceChildren:noop,removeChild:noop,setAttribute:noop,getAttribute:()=>'',querySelectorAll:()=>[],querySelector:()=>element(),getContext:()=>canvas,getBoundingClientRect:()=>({width:640,height:400,left:0,top:0}),click:noop,select:noop,width:640,height:400,scrollHeight:0},seed)}
    function descendants(node){return [node,...(node.children||[]).flatMap(descendants)]}
    const elements=Object.fromEntries(Object.entries(elementSeeds).map(([id,seed])=>[id,element(seed)]));
    const document={getElementById:id=>elements[id]||descendants(document.body).find(n=>n.id===id)||null,createElement:tag=>element({tagName:tag.toUpperCase()}),querySelectorAll:()=>[],querySelector:()=>element(),body:element(),execCommand:noop};
    const window={location:{protocol:'http:',hostname:'localhost',origin:'http://localhost:8080'},addEventListener:(name,cb)=>events[name]=cb,fetch:async()=>({ok:true,status:200,json:async()=>({status:'ok'}),headers:{get:()=> 'application/json'}})};
    const localStorage={getItem:()=>null,setItem:noop};
    const navigator={clipboard:{writeText:async()=>{}}};
    const performance={now:()=>1};
    const requestAnimationFrame=noop,setInterval=noop,clearInterval=noop,setTimeout=noop,clearTimeout=noop;
    const console={log:noop,error:noop,warn:noop};
    class AbortController{constructor(){this.signal={}}abort(){}}
    function btoa(s){return s} function atob(s){return s}
    ''')
    script=h.split('  <script>\n',1)[1].rsplit('  </script>',1)[0]
    c.eval(script)
    c.eval('events.DOMContentLoaded()')
    for i in range(100):
     if not c.execute_pending_job():break
    return c


@unittest.skipIf(quickjs is None, "Install requirements-dev.txt for dashboard runtime checks")
class DashboardRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.context = dashboard_context()

    def settle(self, expression):
        self.context.eval(expression)
        for _ in range(100):
            if not self.context.execute_pending_job():
                break

    def test_startup_detects_server_health(self):
        self.assertEqual(self.context.eval('window.OmniBackendClient.mode'), 'LIVE_PYTHON_HTTP_SERVER')

    def test_http_errors_never_become_virtual_success(self):
        self.settle("""
          window.fetch = async () => ({ok:false,status:401,
            headers:{get:()=> 'application/json'},json:async()=>({error:'Valid bearer API key required'})});
          window.OmniBackendClient.request('GET','/api/state').then(r=>globalThis.result=r);
        """)
        self.assertFalse(self.context.eval('result.ok'))
        self.assertEqual(self.context.eval('result.status'), 401)
        self.assertEqual(self.context.eval('result.mode'), 'LIVE_HTTP')

    def test_connection_failure_returns_503(self):
        self.settle("""
          window.fetch = async () => {throw new Error('Disconnected')};
          window.OmniBackendClient.request('GET','/api/state').then(r=>globalThis.result=r);
        """)
        self.assertFalse(self.context.eval('result.ok'))
        self.assertEqual(self.context.eval('result.status'), 503)
        self.assertEqual(self.context.eval('result.mode'), 'DISCONNECTED')

    def test_metrics_text_is_preserved(self):
        self.settle("""
          window.fetch = async () => ({ok:true,status:200,
            headers:{get:()=> 'text/plain'},text:async()=> 'omnigenesis_omega_quotient 1.5'});
          window.OmniBackendClient.request('GET','/metrics').then(r=>globalThis.result=r);
        """)
        self.assertTrue(self.context.eval('result.ok'))
        self.assertEqual(self.context.eval('result.data.content'), 'omnigenesis_omega_quotient 1.5')

    def test_setup_password_mismatch_is_caught_before_network(self):
        self.settle("""
          globalThis.form = descendants(document.body).find(n=>n.tagName==='FORM');
          descendants(form).find(n=>n.name==='password').value='a sufficiently long password';
          descendants(form).find(n=>n.name==='confirm_password').value='a different long password';
          globalThis.requests=0;
          window.fetch=async()=>{requests++; throw new Error('Should not submit')};
          form.handlers.submit({preventDefault:()=>{}});
        """)
        self.assertEqual(self.context.eval('requests'), 0)
        self.assertIn("don't match", self.context.eval("document.getElementById('platform-connection-status').textContent"))

    def test_setup_displays_recovery_codes_and_clears_secrets(self):
        self.settle("""
          globalThis.form=descendants(document.body).find(n=>n.tagName==='FORM');
          for(const n of descendants(form)){
            if(n.name==='email')n.value='Owner@Example.com';
            if(n.name==='setup_key')n.value='one-time-key';
            if(n.name==='password'||n.name==='confirm_password')n.value='a sufficiently long password';
          }
          window.fetch=async(url,opts)=>({ok:true,status:200,headers:{get:()=> 'application/json'},
            json:async()=>url.endsWith('/api/health')?{status:'ok'}:{username:'owner@example.com',recovery_codes:['secret-recovery-code']}});
          form.handlers.submit({preventDefault:()=>{}});
        """)
        self.assertTrue(self.context.eval("descendants(document.body).some(n=>n.tagName==='PRE'&&n.textContent.includes('secret-recovery-code')&&!n.hidden)"))
        self.assertTrue(self.context.eval("descendants(form).filter(n=>n.tagName==='INPUT').every(n=>n.value==='')"))
