// Independent from the offer cycle and WhatsApp state.
export function createSendAiExporter(invoke, changed=()=>{}){
  const entries=new Map();
  let ready=false,checking=false,busy=false;
  const key=offer=>JSON.stringify([offer.name,offer.content]);
  function status(offer){
    const entry=entries.get(key(offer));
    const valid=Boolean(offer.name?.trim()&&/https?:\/\/\S+/i.test(offer.content||""));
    return {
      disabled:!ready||busy||!valid||entry?.done===true,
      label:entry?.pending?"Exportando…":entry?.done?"✓ Exportado":"Exportar SendAi",
      title:!valid?"Esta oferta não tem texto com link para exportar.":entry?.done?"Post salvo na biblioteca do SendAiPlus.":!ready?"Abra o SendAiPlus atualizado para exportar.":"Criar um post ativo do tipo Texto com link no SendAiPlus.",
    };
  }
  return {
    status,
    get ready(){return ready},
    async refresh(){
      if(checking||busy)return;
      checking=true;
      try{ready=(await invoke("backend_request",{command:"get_sendai_status",payload:{}})).ready===true}
      catch{ready=false}
      finally{checking=false;changed()}
    },
    async export(offer){
      if(status(offer).disabled)return false;
      const id=key(offer),entry=entries.get(id)||{id:crypto.randomUUID()};
      entries.set(id,entry);entry.pending=true;busy=true;changed();
      try{
        const result=await invoke("backend_request",{command:"export_sendai",payload:{id:entry.id,name:offer.name,content:offer.content}});
        if(result.postId!==entry.id)throw new Error("O SendAiPlus não confirmou esta oferta. Tente novamente.");
        entry.done=true;
        return true;
      }finally{entry.pending=false;busy=false;changed()}
    },
  };
}
